"""Gera a versão Word (.docx) do artigo a partir dos fontes LaTeX.

Uso (a partir da pasta artigo/, depois de compilar o PDF com pdflatex + bibtex):
    python3 ../codigo/gera_docx.py

O script lê main.aux (números de tabelas, figuras, equações e seções) e main.bbl
(rótulos autor-ano e lista de referências gerados pelo natbib/plainnat-pt), de modo
que as citações e as referências do Word ficam idênticas às do PDF. Depois converte
o texto com o pandoc, usando um documento de referência com Times New Roman 12,
espaçamento 1,5 e margens da ABNT.
"""
import re
import subprocess
import sys
from pathlib import Path

ART = Path.cwd()
if not (ART / "main.tex").exists():
    sys.exit("Execute a partir da pasta artigo/ (onde está main.tex).")
OUT_DIR = ART.parent
SAIDA = OUT_DIR / "232045821_P2_FSP.docx"
TMP = ART / "_docx_tmp"
TMP.mkdir(exist_ok=True)

aux = (ART / "main.aux").read_text(encoding="utf8", errors="ignore")
bbl = (ART / "main.bbl").read_text(encoding="utf8", errors="ignore")

# ------------------------------------------------------------------ rótulos
labels = {}
for m in re.finditer(r"\\newlabel\{([^}]+)\}\{\{([^}]*)\}", aux):
    labels[m.group(1)] = m.group(2)

# ------------------------------------------------------------------ citações (natbib)
cit = {}
for m in re.finditer(r"\\bibitem\[(.+?)\]\{([^}]+)\}", bbl, re.S):
    lab, key = re.sub(r"\s+", " ", m.group(1)), m.group(2)
    lab = lab.replace("{", "").replace("}", "").replace("~", " ")
    mm = re.match(r"(.*?)\((\d{4}[a-z]?)\)", lab)
    autores, ano = mm.group(1).strip(), mm.group(2)
    cit[key] = (autores, ano)


def citet(keys):
    return "; ".join(f"{cit[k][0]} ({cit[k][1]})" for k in keys)


def citep(keys):
    return "(" + "; ".join(f"{cit[k][0]}, {cit[k][1]}" for k in keys) + ")"


def troca_citacoes(s):
    def f(m):
        cmd, keys = m.group(1), [k.strip() for k in m.group(2).split(",")]
        for k in keys:
            if k not in cit:
                raise KeyError(k)
        return citet(keys) if cmd == "citet" else citep(keys)

    return re.sub(r"\\(citet|citep)\{([^}]+)\}", f, s)


# ------------------------------------------------------------------ texto
def expande_inputs(s):
    def f(m):
        nome = m.group(1)
        p = ART / (nome if nome.endswith(".tex") else nome + ".tex")
        return expande_inputs(p.read_text(encoding="utf8")) if p.exists() else ""

    s = re.sub(r"\\IfFileExists\{[^}]+\}\{\\input\{([^}]+)\}\}\{\}", lambda m: "\\input{" + m.group(1) + "}", s)
    return re.sub(r"\\input\{([^}]+)\}", f, s)


main = (ART / "main.tex").read_text(encoding="utf8")
corpo = main.split("\\input{secoes/01_introducao}", 1)[1].split("\\bibliographystyle", 1)[0]
corpo = "\\input{secoes/01_introducao}" + corpo
corpo = re.sub(r"(?m)^%.*$", "", corpo)
corpo = expande_inputs(corpo)
corpo = re.sub(r"(?<!\\)%.*$", "", corpo, flags=re.M)

# figura condicional da bibliometria: \IfFileExists{...}{%  \begin{figure} ... \end{figure}}{}
corpo = re.sub(r"\\IfFileExists\{figuras/[^}]+\}\{\s*(\\begin\{figure\}.*?\\end\{figure\})\}\{\}", r"\1", corpo, flags=re.S)

corpo = troca_citacoes(corpo)


def equacao(m):
    rot = re.search(r"\\label\{([^}]+)\}", m.group(1)).group(1)
    eq = re.sub(r"\\label\{[^}]+\}", "", m.group(1)).strip().rstrip(",.")
    return "\n$$" + eq + "\\qquad (" + labels[rot] + ")$$\n"


corpo = re.sub(r"\\begin\{equation\}(.*?)\\end\{equation\}", equacao, corpo, flags=re.S)
corpo = re.sub(r"\\eqref\{([^}]+)\}", lambda m: "(" + labels[m.group(1)] + ")", corpo)
corpo = re.sub(r"\\ref\{([^}]+)\}", lambda m: labels[m.group(1)], corpo)
corpo = corpo.replace("~", " ")
corpo = re.sub(r"\\label\{(?:sec|tab|fig):[^}]+\}", "", corpo)

# figuras: PDF -> PNG; legenda numerada; fonte abaixo
nfig = [0]


def figura(m):
    bloco = m.group(0)
    nfig[0] += 1
    img = re.search(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", bloco).group(1)
    img = re.sub(r"\.pdf$", ".png", img)
    cap = re.search(r"\\caption\{(.*?)\}\s*\n", bloco, re.S).group(1)
    fonte = re.search(r"\\fonte\{(.*)\}\s*\n\\end\{figure\}", bloco, re.S)
    txt = f"\n\n\\begin{{center}}\\textbf{{Figura {nfig[0]}:}} {cap}\\end{{center}}\n\n"
    txt += f"\\begin{{center}}\\includegraphics[width=6in]{{{ART / img}}}\\end{{center}}\n\n"
    if fonte:
        txt += f"\\FONTEPAR{{Fonte: {fonte.group(1)}}}\n\n"
    return txt


corpo = re.sub(r"\\begin\{figure\}.*?\\end\{figure\}", figura, corpo, flags=re.S)

# tabelas: legenda numerada acima, notas e fonte abaixo, tabularx -> tabular
ntab = [0]


def tabela(m):
    bloco = m.group(0)
    ntab[0] += 1
    cap = re.search(r"\\caption\{(.*?)\}(?:\\label\{[^}]*\})?\s*\n", bloco, re.S).group(1)
    tab = re.search(r"\\begin\{(tabularx?)\}(.*?)\\end\{\1\}", bloco, re.S)
    amb, conteudo = tab.group(1), tab.group(2)
    if amb == "tabularx":
        conteudo = re.sub(r"^\{\\textwidth\}", "", conteudo)
    spec_m = re.match(r"\s*\{((?:[^{}]|\{[^{}]*\})*)\}", conteudo)
    spec = spec_m.group(1)
    ncol = len(re.findall(r"[lcrXp]", re.sub(r"\{[^{}]*\}", "", spec)))
    conteudo = conteudo[spec_m.end():]
    conteudo = re.sub(r"\\cmidrule(\([a-z]+\))?\{[^}]*\}", "", conteudo)
    conteudo = conteudo.replace("\\quad ", "    ")
    depois = bloco[tab.end():]
    notas = []
    for n in re.findall(r"\\parbox\{\\textwidth\}\{\\scriptsize (.*)\}\s*\n", depois, re.S):
        notas.append(n.strip())
    for n in re.findall(r"\\item (.*?)\n\\end\{tablenotes\}", depois, re.S):
        notas.append(n.strip())
    for n in re.findall(r"\\fonte\{(.*)\}\s*\n", depois):
        notas.append("Fonte: " + n.strip())
    txt = f"\n\n\\begin{{center}}\\textbf{{Tabela {ntab[0]}:}} {cap}\\end{{center}}\n\n"
    txt += "\\begin{tabular}{" + "l" * ncol + "}" + conteudo + "\\end{tabular}\n\n"
    for n in notas:
        txt += f"\\NOTAPAR{{{n}}}\n\n"
    return txt


corpo = re.sub(r"\\begin\{table\}.*?\\end\{table\}", tabela, corpo, flags=re.S)

# seções não numeradas e declarações
corpo = corpo.replace("\\addcontentsline{toc}{section}{Declaração sobre o uso de inteligência artificial}", "")

# ------------------------------------------------------------------ referências a partir do .bbl
refs = []
for bloco in re.split(r"\\bibitem\[", bbl)[1:]:
    corpo_ref = re.sub(r"^.*?\]\{[^}]+\}\s*", "", bloco, count=1, flags=re.S)
    corpo_ref = corpo_ref.split("\\end{thebibliography}")[0]
    corpo_ref = corpo_ref.replace("\\newblock", " ").replace("\\penalty0", "")
    corpo_ref = re.sub(r"\\doi\{([^}]+)\}", r"doi: \1", corpo_ref)
    corpo_ref = re.sub(r"\\natexlab\{([^}]*)\}", r"\1", corpo_ref)
    corpo_ref = re.sub(r"\\urlprefix", "", corpo_ref)
    corpo_ref = re.sub(r"\s+", " ", corpo_ref).strip()
    refs.append("\\REFPAR{" + corpo_ref + "}")
referencias = "\n\n\\section*{REFERÊNCIAS}\n\n" + "\n\n".join(refs)

# ------------------------------------------------------------------ resumo
resumo = (ART / "secoes/00_resumo.tex").read_text(encoding="utf8")
resumo = resumo.replace("\\begin{abstract}", "").replace("\\end{abstract}", "")
resumo = resumo.replace("\\vspace{0.5em}", "").replace("\\noindent", "")
resumo = resumo.replace("\\\\\n", "\n")
resumo = re.sub(r"(\\textbf\{(?:Palavras-chave|Classificação JEL|Dados e códigos):\}[^\n]*)", r"\\begin{esq}\1\\end{esq}", resumo)

cabecalho = r"""
\begin{capa}
\includegraphics[width=2.7in]{""" + str(ART / "figuras" / "logo_unb.png") + r"""}

João Gabriel Maréco Galhas --- Matrícula 232045821

Universidade de Brasília (UnB) --- Finanças do Setor Público (CCA0169), Turma 01, 2026.2

Professor: Lucas Oliveira Gomes Ferreira

\textbf{Dependência de transferências, autonomia fiscal e efeito \textit{flypaper}: Barreiras e Camaçari (BA) e os governos locais da Hungria (2016--2025)}

Brasília, outubro de 2026
\end{capa}

\begin{center}SUMARIOMARCA\end{center}

\begin{center}\textbf{RESUMO}\end{center}

""" + resumo

doc = (
    "\\documentclass{article}\n"
    "\\newcommand{\\fonte}[1]{Fonte: #1}\n"
    "\\begin{document}\n" + cabecalho + corpo + referencias + "\n\\end{document}\n"
)
doc = doc.replace("\\FONTEPAR{", "\\NOTAPAR{")
# marcadores de parágrafo com estilo próprio (tratados num filtro Lua)
doc = re.sub(r"\\NOTAPAR\{", r"\\begin{nota}", doc)
doc = re.sub(r"\\REFPAR\{", r"\\begin{refe}", doc)


def fecha(doc, abre, fecha_amb):
    out, i = [], 0
    while True:
        j = doc.find(abre, i)
        if j < 0:
            out.append(doc[i:])
            break
        out.append(doc[i:j + len(abre)])
        k, prof = j + len(abre), 1
        while prof:
            c = doc[k]
            if c == "{" and doc[k - 1] != "\\":
                prof += 1
            elif c == "}" and doc[k - 1] != "\\":
                prof -= 1
            k += 1
        out.append(doc[j + len(abre):k - 1] + fecha_amb)
        i = k
    return "".join(out)


doc = fecha(doc, "\\begin{nota}", "\\end{nota}")
doc = fecha(doc, "\\begin{refe}", "\\end{refe}")
(TMP / "artigo_word.tex").write_text(doc, encoding="utf8")

filtro = TMP / "estilos.lua"
filtro.write_text(
    r'''
function Div(el)
  if el.classes:includes("nota") then
    el.attributes["custom-style"] = "Nota"
    return el
  elseif el.classes:includes("refe") then
    el.attributes["custom-style"] = "Referencia"
    return el
  elseif el.classes:includes("capa") then
    el.attributes["custom-style"] = "Capa"
    return el
  elseif el.classes:includes("esq") then
    el.attributes["custom-style"] = "Esquerda"
    return el
  elseif el.classes:includes("center") then
    el.attributes["custom-style"] = "Centralizado"
    return el
  end
end
function Table(el)
  return el
end
''',
    encoding="utf8",
)

ref_docx = TMP / "referencia.docx"
subprocess.run(["python3", str(ART.parent / "codigo" / "gera_reference_docx.py"), str(ref_docx)], check=True)
subprocess.run(
    [
        "pandoc", str(TMP / "artigo_word.tex"), "-f", "latex", "-t", "docx",
        "--reference-doc", str(ref_docx), "--lua-filter", str(filtro),
        "-M", "lang=pt-BR", "--number-sections", "-o", str(SAIDA),
    ],
    check=True,
)
subprocess.run(["python3", str(ART.parent / "codigo" / "ajusta_docx.py"), str(SAIDA)], check=True)
subprocess.run(["python3", str(ART.parent / "codigo" / "paginas_sumario.py"), str(SAIDA)], check=False)
print("Gerado:", SAIDA, "| figuras:", nfig[0], "| tabelas:", ntab[0], "| referências:", len(refs))
