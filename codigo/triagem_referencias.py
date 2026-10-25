"""
Triagem das referências: junta as exportações da Scopus e do Portal CAPES com a lista mestra,
remove duplicatas, classifica por eixo temático e prioridade e gera:
  referencias/triagem_referencias.csv   (separador ';' para abrir no Excel em português)
  referencias/candidatas_prioritarias.bib (entradas BibTeX dos artigos prioritários, para o Overleaf)

Critério do trabalho: artigos de periódico dos últimos 10 anos (2016-2026); anteriores só se forem
clássicos (muito citados ou centrais ao tema) - marcados como "clássico".
A prioridade é uma SUGESTÃO automática a partir do título: confira lendo o resumo.
Uso: python codigo/triagem_referencias.py
"""
import os
import re
import math
import glob
import unicodedata
import pandas as pd

BIB = os.path.join("data", "bibliometria")
OUT = "referencias"
ANO_MIN = 2016


def campos(entrada):
    def g(k):
        m = re.search(r"\n\s*" + k + r"\s*=\s*\{(.*?)\},?\s*\n", entrada, re.S)
        return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
    cit = re.search(r"Cited by: (\d+)", entrada)
    return {"tipo": g("type") or entrada.split("{", 1)[0].strip().lower(), "autores": g("author"),
            "ano": int(g("year") or 0), "titulo": g("title"), "periodico": g("journal"), "volume": g("volume"),
            "numero": g("number"), "paginas": g("pages"), "doi": g("doi").lower(),
            "citacoes_scopus": int(cit.group(1)) if cit else None,
            "palavras_chave": g("author_keywords"), "resumo": g("abstract")}


def le_bib(arquivo, origem):
    s = open(arquivo, encoding="utf-8").read()
    out = []
    for e in re.split(r"\n@", "\n" + s)[1:]:
        r = campos(e)
        r["origem"] = origem
        r["bibtex"] = "@" + e.strip() if origem.startswith("Scopus") else ""
        out.append(r)
    return out


def chave(r):
    if r.get("doi") and re.match(r"^10\.\d{4,}/\S{4,}", r["doi"]):
        return r["doi"]
    t = unicodedata.normalize("NFKD", str(r.get("titulo", "")).lower())
    return re.sub(r"[^a-z0-9]", "", t)[:60]


def pontua(r):
    t = ((r["titulo"] or "") + " " + str(r.get("palavras_chave") or "")).lower()
    p = 0
    regras = [(r"fly ?paper|sinek k", 4), (r"fiscal illusion|ilus[ãa]o fiscal|ilusi fiskal|grant illusion", 4),
              (r"transfer|grant|repasse|transfer[êe]ncia", 2),
              (r"own.?(source )?revenue|local revenue|tax effort|fiscal effort|esfor[çc]o|arrecada|revenue generation|tax collection", 2),
              (r"brazil|brasil", 2), (r"hungar", 3),
              (r"czech|slovak|poland|polish|central and eastern|post-?socialist|post-?communist|visegr|romania|croatia|sloven", 1),
              (r"decentrali|federal", 1), (r"municipal|local government|munic[íi]pio|local", 1)]
    for rx, w in regras:
        if re.search(rx, t):
            p += w
    if r.get("citacoes_scopus"):
        p += min(3, math.log10(r["citacoes_scopus"] + 1))
    return round(p, 2)


def eixo(r):
    t = ((r["titulo"] or "") + " " + str(r.get("palavras_chave") or "")).lower()
    for rx, nome in [(r"hungar|czech|slovak|poland|polish|central and eastern|post-?socialist|post-?communist|visegr|romania|croatia|sloven|europe",
                      "6. Governos locais na Europa Central e Oriental / Hungria"),
                     (r"fiscal illusion|ilus[ãa]o fiscal|ilusi fiskal|grant illusion", "3. Ilusão fiscal"),
                     (r"fly ?paper|sinek k", "1. Efeito flypaper"),
                     (r"own.?(source )?revenue|local revenue|tax effort|fiscal effort|esfor[çc]o|arrecada|revenue generation|tax collection",
                      "4. Transferências e esforço fiscal"),
                     (r"political|election|elei|alignment|partisan|pol[íi]tic", "5. Economia política das transferências"),
                     (r"brazil|brasil|munic[íi]pios", "2. Transferências no Brasil"),
                     (r"decentrali|federal", "7. Federalismo e descentralização")]:
        if re.search(rx, t):
            return nome
    return "8. Outros (decidir)"


def main():
    regs = []
    for f in sorted(glob.glob(os.path.join(BIB, "scopus_*.bib"))):
        regs += le_bib(f, "Scopus: " + os.path.basename(f))
    for f in sorted(glob.glob(os.path.join(BIB, "capes_*.bib"))):
        regs += le_bib(f, "CAPES: " + os.path.basename(f) + " (metadados a conferir)")
    lm = pd.read_csv(os.path.join(OUT, "lista_mestra_referencias.csv"))
    for _, x in lm.iterrows():
        doi = re.search(r"10\.\d{4,}/[^\s,;]+", str(x.referencia))
        regs.append({"tipo": "article", "autores": "", "ano": int(x.ano) if pd.notna(x.ano) else 0,
                     "titulo": str(x.referencia), "periodico": "", "volume": "", "numero": "", "paginas": "",
                     "doi": doi.group(0).lower().rstrip(".") if doi else "", "citacoes_scopus": None,
                     "origem": f"Lista mestra ({x.origem})", "bibtex": "", "palavras_chave": "", "resumo": ""})
    U = {}
    for r in regs:
        k = chave(r)
        if k in U:
            u = U[k]
            if r["origem"] not in u["origem"]:
                u["origem"] += " | " + r["origem"]
            for c in ["citacoes_scopus", "bibtex", "periodico", "autores", "palavras_chave", "resumo"]:
                if not u.get(c) and r.get(c):
                    u[c] = r[c]
            # prefere o registro BibTeX que traz o resumo (exportação completa)
            if r.get("bibtex") and "abstract = {" in r["bibtex"] and "abstract = {" not in (u.get("bibtex") or ""):
                u["bibtex"] = r["bibtex"]; u["resumo"] = r.get("resumo") or u.get("resumo")
                u["palavras_chave"] = r.get("palavras_chave") or u.get("palavras_chave")
                u["citacoes_scopus"] = r.get("citacoes_scopus") or u.get("citacoes_scopus")
            if u["origem"].startswith("Lista") and r["origem"].startswith(("Scopus", "CAPES")):
                u["titulo"] = r["titulo"]
        else:
            U[k] = dict(r)
    # 2ª passada: a lista mestra guarda a referência inteira como texto; se o título de um registro da
    # Scopus/CAPES aparece dentro desse texto, é o mesmo artigo (junta e fica com os metadados da base)
    norm = lambda x: re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", str(x).lower()))
    bases = [(k, norm(u["titulo"])) for k, u in U.items() if not u["origem"].startswith("Lista") and len(norm(u["titulo"])) > 25]
    for k in [k for k, u in U.items() if u["origem"].startswith("Lista")]:
        ref = norm(U[k]["titulo"])
        alvo = next((kb for kb, tb in bases if tb[:80] in ref), None)
        if alvo:
            U[alvo]["origem"] += " | " + U[k]["origem"]
            del U[k]
    d = pd.DataFrame(U.values())
    d = d[~d.tipo.str.lower().isin(["book chapter", "conference paper", "book", "dissertation", "conference review"])]
    d["pontos"] = d.apply(pontua, axis=1)
    d["eixo"] = d.apply(eixo, axis=1)
    d["recente_2016_mais"] = d.ano >= ANO_MIN
    # Clássicos fundadores citados de qualquer forma (autores de referência do tema)
    FUNDADORES = r"Hines|Thaler|Oates|Gramlich|Courant|Fisher, R\. C|Buchanan|Puviani|Dollery"
    fund = d.titulo.str.contains(FUNDADORES, na=False) | d.autores.fillna("").str.contains(FUNDADORES)
    d["classico"] = (~d.recente_2016_mais) & ((d.citacoes_scopus.fillna(0) >= 100) | (d.pontos >= 8) | fund)
    def prioridade(x):
        if not x.recente_2016_mais:
            return "Clássico (usar se indispensável)" if x.classico else "Fora do período"
        return "A - ler inteiro" if x.pontos >= 6 else "B - ler resumo e conclusão" if x.pontos >= 3.5 else "C - reserva"
    d["prioridade"] = d.apply(prioridade, axis=1)
    d["link"] = d.doi.apply(lambda s: f"https://doi.org/{s}" if s else "")
    d["na_lista_mestra"] = d.origem.str.contains("Lista mestra")
    d["status_leitura"] = ""; d["achado_em_1_frase"] = ""; d["onde_uso_no_artigo"] = ""
    ordem = {"A - ler inteiro": 0, "B - ler resumo e conclusão": 1, "C - reserva": 2,
             "Clássico (usar se indispensável)": 3, "Fora do período": 4}
    d["_o"] = d.prioridade.map(ordem)
    d = d.sort_values(["_o", "eixo", "pontos"], ascending=[True, True, False])
    cols = ["prioridade", "eixo", "ano", "autores", "titulo", "periodico", "volume", "numero", "paginas", "doi", "link",
            "citacoes_scopus", "pontos", "status_leitura", "achado_em_1_frase", "onde_uso_no_artigo", "palavras_chave",
            "resumo", "origem", "na_lista_mestra"]
    d[cols].to_csv(os.path.join(OUT, "triagem_referencias.csv"), sep=";", index=False, encoding="utf-8-sig")
    # BibTeX dos prioritários (A, B e clássicos) que vieram da Scopus
    sel = d[d.prioridade.str[0].isin(["A", "B", "C"]) | (d.prioridade.str.startswith("Clássico"))]
    # Chaves BibTeX sem acento e sem repetição (o BibTeX 8-bit do Overleaf pode falhar com acentos)
    vistas = set()
    def limpa(b):
        m = re.match(r"(@\w+\{)([^,]+),", b)
        if not m:
            return None
        k = re.sub(r"[^A-Za-z0-9_-]", "", unicodedata.normalize("NFKD", m.group(2)).encode("ascii", "ignore").decode())
        base, i = k, 1
        while k in vistas:
            i += 1; k = f"{base}{chr(96 + i)}"
        vistas.add(k)
        corpo = b[m.end():]
        # compatibilidade com pdfLaTeX: normaliza (ex.: ＊ -> *), remove títulos traduzidos entre colchetes
        # e caracteres fora do latim estendido (cirílico, chinês etc.), que travariam a compilação
        corpo = unicodedata.normalize("NFKC", corpo)
        corpo = re.sub(r"(title\s*=\s*\{[^\n]*?);\s*\[[^\]]*\](\},)", r"\1\2", corpo)
        ok = set("–—‘’“”…•")
        corpo = "".join(ch for ch in corpo if ord(ch) < 0x180 or ch in ok)
        # mantém só os campos que entram na referência (o resto alongaria a lista com URL, ISSN, "Cited by"...)
        manter = {"author", "title", "year", "journal", "volume", "number", "pages", "doi"}
        campos = re.findall(r"\n\s*(\w+)\s*=\s*(\{.*?\}),?(?=\s*\n\s*\w+\s*=|\s*\n?\}\s*$)", corpo, re.S)
        corpo = "\n" + ",\n".join(f"\t{c} = {v}" for c, v in campos if c.lower() in manter) + "\n}"
        return m.group(1) + k + "," + corpo
    d["chave_bibtex"] = ""
    with open(os.path.join(OUT, "candidatas_prioritarias.bib"), "w", encoding="utf-8") as f:
        for idx, b in sel.bibtex.items():
            if b:
                nb = limpa(b)
                if nb:
                    f.write(nb + "\n\n")
                    d.loc[idx, "chave_bibtex"] = re.match(r"@\w+\{([^,]+),", nb).group(1)
    cols.insert(4, "chave_bibtex")
    d[cols].to_csv(os.path.join(OUT, "triagem_referencias.csv"), sep=";", index=False, encoding="utf-8-sig")
    print(d.prioridade.value_counts().to_string())
    print(d[d.recente_2016_mais].groupby("eixo").prioridade.value_counts().unstack(fill_value=0).to_string())
    print("Entradas BibTeX gravadas:", int((sel.bibtex != "").sum()))


if __name__ == "__main__":
    main()
