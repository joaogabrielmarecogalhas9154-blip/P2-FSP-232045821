"""
P2 - Finanças do Setor Público (UnB) - Tratamento dos dados dos municípios
Entrada : data/raw/   (gerado por coleta_municipios.py; NÃO é alterado)
Saída   : data/tratados/  (painel tratado + log de qualidade)

Decisões metodológicas (registrar no artigo e no dicionário de variáveis):
 - Receitas: DCA Anexo I-C, coluna "Receitas Brutas Realizadas" (sem somar linhas:
   cada variável é UMA conta exata da hierarquia). Deduções do FUNDEB em coluna própria.
 - Despesas: DCA Anexo I-D (natureza) e I-E (função), coluna "Despesas Empenhadas".
 - Deflator: média anual do IPCA (número-índice, SIDRA 1737), preços de ANO_BASE.
 - População: estimativa IBGE (SIDRA 6579). Anos ausentes (2022, 2023) são preenchidos de
   forma explícita e sinalizada (Censo 2022; interpolação linear em 2023), nunca com zero.
 - Dado ausente permanece NaN.
"""
import os
import numpy as np
import pandas as pd

from config import MUNICIPIOS as MUN, ANO_INI, ANO_FIM, ANO_BASE
from rubricas_receita import extrai, de_dca_api, CONCEITOS

RAW = os.path.join("data", "raw")
OUT = os.path.join("data", "tratados")
os.makedirs(OUT, exist_ok=True)

# Período, base de preços e municípios vêm de config.py (PIB municipal só existe até 2023).


def censo_2022():
    """Pop. do Censo 2022: baixada da SIDRA 4714 (raw) ou, se falhar, data/manual/censo2022.csv."""
    f1 = os.path.join(RAW, "sidra_censo2022.csv")
    f2 = os.path.join("data", "manual", "censo2022.csv")
    if os.path.exists(f1):
        c = pd.read_csv(f1)
        c = c.rename(columns={"Município (Código)": "cod_ibge"})
        c["populacao"] = pd.to_numeric(c["Valor"], errors="coerce")
        out = c.dropna(subset=["populacao"]).set_index("cod_ibge")["populacao"].to_dict()
    elif os.path.exists(f2):
        c = pd.read_csv(f2)
        out = c.set_index("cod_ibge")["populacao"].to_dict()
    else:
        raise FileNotFoundError("Sem Censo 2022: rode a coleta ou crie data/manual/censo2022.csv (cod_ibge,populacao)")
    faltam = [k for k in MUN if k not in out]
    if faltam:
        raise ValueError(f"Censo 2022 ausente para {faltam}")
    return {int(k): float(v) for k, v in out.items()}


CENSO_2022 = censo_2022()


# ----------------------------------------------------------------- helpers
def segs(cod, prefixo):
    """Segmentos numéricos de um cod_conta como 'RO1.7.0.0.00.0.0' ou 'DO3.0.00.00.00.00'.
    Funciona igual para o formato antigo (2015-2017: 'RO1.7.0.0.00.00.00') e o novo (2018+)."""
    if not isinstance(cod, str) or not cod.startswith(prefixo):
        return None
    try:
        return [int(x) for x in cod[len(prefixo):].split(".")]
    except ValueError:
        return None


def nivel(cod, prefixo, alvo):
    """True se o código é exatamente o nível `alvo` (ex.: [1,7]) com todo o resto zerado."""
    s = segs(cod, prefixo)
    return s is not None and s[:len(alvo)] == list(alvo) and all(v == 0 for v in s[len(alvo):])


def valor_unico(df, mascara, nome, ano, mun, log):
    """Retorna o valor de EXATAMENTE uma linha. Se houver 0 -> NaN; se >1 -> erro registrado."""
    sub = df[mascara]
    if len(sub) == 1:
        return float(sub["valor"].iloc[0])
    log.append({"municipio": mun, "ano": ano, "variavel": nome,
                "problema": f"{len(sub)} linhas encontradas (esperado 1)"})
    return np.nan


# ----------------------------------------------------------------- IPCA / deflator
def deflator():
    d = pd.read_csv(os.path.join(RAW, "sidra_ipca_indice.csv"))
    d["mes"] = d["Mês (Código)"].astype(int)
    d["ano"] = d["mes"] // 100
    d["idx"] = pd.to_numeric(d["Valor"], errors="coerce")
    d = d[d["idx"] > 0]
    g = d.groupby("ano")["idx"].agg(ipca_media_anual="mean", meses="count", ipca_dez="last")
    g = g[g["meses"] == 12].copy()                       # só anos completos
    g["fator_deflator"] = g.loc[ANO_BASE, "ipca_media_anual"] / g["ipca_media_anual"]
    return g.reset_index()


# ----------------------------------------------------------------- população
def populacao():
    p = pd.read_csv(os.path.join(RAW, "sidra_populacao.csv"))
    p = p.rename(columns={"Município (Código)": "cod_ibge", "Ano": "ano"})
    p["populacao"] = pd.to_numeric(p["Valor"], errors="coerce")
    p = p[["cod_ibge", "ano", "populacao"]].copy()
    p["pop_fonte"] = "IBGE estimativa (SIDRA 6579)"
    linhas = []
    for cod in MUN:
        s = p[p.cod_ibge == cod].set_index("ano")
        anos = range(ANO_INI, ANO_FIM + 1)
        for a in anos:
            if a in s.index and pd.notna(s.loc[a, "populacao"]):
                continue
            if a == 2022:
                linhas.append({"cod_ibge": cod, "ano": 2022, "populacao": CENSO_2022[cod],
                               "pop_fonte": "Censo 2022 (IBGE) - ausente na tab. 6579"})
            elif a == 2023 and 2024 in s.index:
                v = (CENSO_2022[cod] + s.loc[2024, "populacao"]) / 2
                linhas.append({"cod_ibge": cod, "ano": 2023, "populacao": v,
                               "pop_fonte": "INTERPOLADO linear (Censo 2022 e estimativa 2024)"})
    p = pd.concat([p, pd.DataFrame(linhas)], ignore_index=True)
    return p


# ----------------------------------------------------------------- PIB
def pib():
    d = pd.read_csv(os.path.join(RAW, "sidra_pib_municipal.csv"))
    d = d.rename(columns={"Município (Código)": "cod_ibge", "Ano": "ano", "Variável (Código)": "v"})
    d = d[d["Unidade de Medida"] == "Mil Reais"]
    d["valor_num"] = pd.to_numeric(d["Valor"], errors="coerce")
    nomes = {37: "pib_nominal", 543: "impostos_liq_subs", 498: "vab_total", 513: "vab_agro",
             517: "vab_industria", 6575: "vab_servicos", 525: "vab_adm_publica"}
    d = d[d["v"].isin(nomes)]
    w = d.pivot_table(index=["cod_ibge", "ano"], columns="v", values="valor_num", aggfunc="first")
    w = w.rename(columns=nomes) * 1000.0                # mil reais -> reais
    return w.reset_index()


# ----------------------------------------------------------------- DCA
def dca_rubricas(log):
    dca = pd.read_csv(os.path.join(RAW, "siconfi_dca_bruto.csv"))
    out = []
    for (cod, ano), g in dca.groupby(["cod_ibge", "exercicio"]):
        if not (ANO_INI <= ano <= ANO_FIM):
            continue
        mun = MUN[cod]
        r = g[g.anexo == "DCA-Anexo I-C"]
        rb = r[r.coluna == "Receitas Brutas Realizadas"]
        fu = r[r.coluna == "Deduções - FUNDEB"]
        od = r[r.coluna == "Outras Deduções da Receita"]
        d = g[g.anexo == "DCA-Anexo I-D"]
        db = d[d.coluna == "Despesas Empenhadas"]
        e = g[(g.anexo == "DCA-Anexo I-E") & (g.coluna == "Despesas Empenhadas")]

        linha = {"cod_ibge": cod, "municipio": mun, "ano": ano}
        # Receitas (níveis exatos da natureza de receita)
        # QUEBRA DE SÉRIE: até 2017 as transferências intergovernamentais ficam em 1.7.2
        # (1.7.2.1 = União; 1.7.2.2 = Estados). A partir de 2018: 1.7.1 = União; 1.7.2 = Estados.
        if ano <= 2017:
            uniao, estados = [1, 7, 2, 1], [1, 7, 2, 2]
        else:
            uniao, estados = [1, 7, 1], [1, 7, 2]
        niveis_rec = {"rec_corrente": [1, 0], "rec_tributaria": [1, 1], "rec_transf_correntes": [1, 7],
                      "rec_transf_uniao": uniao, "rec_transf_estados": estados}
        for nome, alvo in niveis_rec.items():
            m = rb.cod_conta.apply(lambda c: nivel(c, "RO", alvo))
            linha[nome] = valor_unico(rb, m, nome, ano, mun, log)
        # Rubricas detalhadas (FPM, cotas de ICMS/IPVA/IPI, ITR, IOF-ouro, IPTU, ISS, ITBI, FUNDEB, SUS...)
        # por código + rótulo, robusto às mudanças do ementário de 2018 e 2022 (ver rubricas_receita.py)
        det, _ = extrai(de_dca_api(rb))
        for k, x in det.items():
            linha[f"rec_{k}"] = x
        # Deduções (mesma conta, outras colunas)
        for nome, base in {"ded_fundeb_corrente": fu, "ded_outras_corrente": od}.items():
            m = base.cod_conta.apply(lambda c: nivel(c, "RO", [1, 0]))
            sub = base[m]
            linha[nome] = float(sub["valor"].iloc[0]) if len(sub) == 1 else np.nan
        # Receita total exceto intra (rótulo muda conforme o ano)
        # rec_total = linha 'TotalReceitas' (mesma definição em todos os anos; contém intra-orçamentárias,
        # assim como desp_total em I-D, o que mantém o resultado orçamentário consistente)
        linha["rec_total"] = valor_unico(rb, rb.cod_conta == "TotalReceitas", "rec_total", ano, mun, log)
        # Dedução do FUNDEB sobre a receita total (a receita bruta NÃO desconta o FUNDEB; a receita
        # líquida do balanço orçamentário desconta). Ausente => NaN (não é trocado por zero).
        linha["ded_fundeb_total"] = valor_unico(fu, fu.cod_conta == "TotalReceitas", "ded_fundeb_total", ano, mun, log)
        # Despesas por natureza (I-D)
        for nome, alvo in {"desp_corrente": [3, 0], "desp_pessoal": [3, 1], "desp_capital": [4, 0]}.items():
            m = db.cod_conta.apply(lambda c: nivel(c, "DO", alvo))
            linha[nome] = valor_unico(db, m, nome, ano, mun, log)
        m = (db.cod_conta == "TotalDespesas") & (db.conta == "Total Geral da Despesa")
        linha["desp_total"] = valor_unico(db, m, "desp_total", ano, mun, log)
        # Despesas por função (I-E): o código da função vem no texto da conta
        for nome, rot in {"desp_educacao": "12 - Educação", "desp_saude": "10 - Saúde"}.items():
            linha[nome] = valor_unico(e, e.conta == rot, nome, ano, mun, log)
        out.append(linha)
    return pd.DataFrame(out)


# ----------------------------------------------------------------- montagem
def main():
    log = []
    ipca = deflator()
    pop = populacao()
    pb = pib()
    rub = dca_rubricas(log)

    df = rub.merge(pop, on=["cod_ibge", "ano"], how="left") \
            .merge(pb, on=["cod_ibge", "ano"], how="left") \
            .merge(ipca[["ano", "ipca_media_anual", "fator_deflator"]], on="ano", how="left")

    # Sinal das deduções: a DCA registra as deduções como valores NEGATIVOS em alguns exercícios (formato antigo,
    # 2014-2016) e POSITIVOS nos demais. Padroniza como magnitude positiva antes de subtrair.
    for c in ["ded_fundeb_corrente", "ded_outras_corrente", "ded_fundeb_total"]:
        df[c] = df[c].abs()

    nominais = ["rec_corrente", "rec_tributaria", "rec_transf_correntes", "rec_transf_uniao",
                "rec_transf_estados", "ded_fundeb_corrente", "rec_total", "desp_corrente",
                "desp_pessoal", "desp_capital", "desp_total", "desp_educacao", "desp_saude", "pib_nominal"]
    nominais += [f"rec_{k}" for k in list(CONCEITOS) + ["transf_incondicionais"]]
    for c in nominais:
        df[f"{c}_real"] = df[c] * df["fator_deflator"]                    # reais de ANO_BASE
        df[f"{c}_real_pc"] = df[f"{c}_real"] / df["populacao"]            # per capita

    # Razões (sem unidade monetária): usam valores nominais do mesmo ano
    df["transf_sobre_rec_corrente"] = df["rec_transf_correntes"] / df["rec_corrente"]
    df["tributaria_sobre_rec_corrente"] = df["rec_tributaria"] / df["rec_corrente"]
    df["impostos_proprios"] = df[["rec_iptu", "rec_iss", "rec_itbi"]].sum(axis=1, min_count=3)  # NaN se faltar algum
    df["transf_incond_sobre_rec_corrente"] = df["rec_transf_incondicionais"] / df["rec_corrente"]
    # Receita corrente sem transferências extraordinárias (ex.: Barreiras 2017, R$ 178,6 mi em
    # "Outras Transferências Multigovernamentais"); usada em testes de sensibilidade
    df["rec_corrente_sem_extraord"] = df["rec_corrente"] - df["rec_outras_multigov"].fillna(0)
    df["transf_liq_fundeb"] = df["rec_transf_correntes"] - df["ded_fundeb_corrente"]
    df["desp_corrente_sobre_pib"] = df["desp_corrente"] / df["pib_nominal"]
    df["rec_tributaria_sobre_pib"] = df["rec_tributaria"] / df["pib_nominal"]
    df["transf_sobre_pib"] = df["rec_transf_correntes"] / df["pib_nominal"]
    df["educacao_sobre_desp_total"] = df["desp_educacao"] / df["desp_total"]
    # Receita líquida do FUNDEB e resultado orçamentário (corrigido: bruta - dedução FUNDEB - despesa empenhada)
    df["rec_total_liq_fundeb"] = df["rec_total"] - df["ded_fundeb_total"]
    df["resultado_orcamentario"] = df["rec_total_liq_fundeb"] - df["desp_total"]
    df["resultado_bruto_sem_deducao"] = df["rec_total"] - df["desp_total"]   # definição anterior, mantida para comparação

    df["regime_classif_receita"] = np.where(df["ano"] <= 2017, "ate_2017", "2018_em_diante")
    df["dummy_pos2018"] = (df["ano"] >= 2018).astype(int)
    df["ano_base_preco"] = ANO_BASE
    df = df.sort_values(["cod_ibge", "ano"]).reset_index(drop=True)
    df.to_csv(os.path.join(OUT, "tratado_municipios.csv"), index=False, encoding="utf-8-sig")

    # Log de qualidade: células vazias por variável + problemas de seleção
    vazios = df.isna().groupby(df["municipio"]).sum().T
    vazios = vazios[(vazios > 0).any(axis=1)]
    vazios.to_csv(os.path.join(OUT, "qualidade_celulas_vazias.csv"), encoding="utf-8-sig")
    pd.DataFrame(log).to_csv(os.path.join(OUT, "qualidade_selecao_contas.csv"), index=False, encoding="utf-8-sig")
    ipca.to_csv(os.path.join(OUT, "deflator_ipca.csv"), index=False, encoding="utf-8-sig")
    print("Linhas:", len(df), "| problemas de seleção:", len(log))
    print("Células vazias por variável:\n", vazios)


if __name__ == "__main__":
    main()
