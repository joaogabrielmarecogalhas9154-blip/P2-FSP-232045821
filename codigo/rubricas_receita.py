"""
Extração de rubricas de receita robusta às mudanças do ementário (2014-2017, 2018-2021, 2022+).

Problema: o código da mesma receita muda ao longo do tempo. Exemplo, FPM:
    até 2017  1.7.2.1.01.02.00  Cota-Parte do Fundo de Participação dos Municípios
    2018-2021 1.7.1.8.01.2.0    (cota mensal) + 1.7.1.8.01.3.0 / .4.0 (parcelas de 1%), sem linha-mãe própria
    2022+     1.7.1.1.51.0.0    Cota-Parte do FPM (linha-mãe) + filhas .1/.2/.3
Solução: cada conceito é identificado por (prefixo do código, expressão no rótulo). Entre as contas
que casam, ficam só as de nível mais alto (descarta-se a conta cuja "mãe" também casou) e somam-se
essas. Assim nunca se somam linhas hierárquicas em duplicidade (lição 2 do projeto).

Testado contra a base do trabalho anterior (2014-2023, Barreiras e Camaçari): ver
codigo/importa_base_original.py e data/original/validacao_extrator.csv.
"""
import re
import numpy as np
import pandas as pd

# conceito: (prefixo do código, regex no rótulo, regex de exclusão ou None)
CONCEITOS = {
    "iptu":            ("1.1", r"Predial e Territorial Urbana", None),
    "itbi":            ("1.1", r"Inter\W*Vivos", None),
    "iss":             ("1.1", r"Servi[çc]os de Qualquer Natureza|ISSQN", None),
    "fpm":             ("1.7", r"Fundo de Participa[çc][ãa]o d[oe]s? Munic|\bFPM\b", None),
    "itr":             ("1.7", r"Territorial Rural", None),
    "icms_cota":       ("1.7", r"Cota-Parte do ICMS|Cota-Parte do Imposto sobre Opera[çc]", r"Desonera"),
    "ipva_cota":       ("1.7", r"Cota-Parte do IPVA|Propriedade de Ve[íi]culos", None),
    "ipi_exp_cota":    ("1.7", r"Cota-Parte do IPI", None),
    "iof_ouro":        ("1.7", r"IOF.{0,5}Ouro|Ouro.{0,40}Ativo Financeiro", None),
    "fundeb":          ("1.7", r"FUNDEB|Manuten[çc][ãa]o e Desenvolvimento da Educa[çc][ãa]o B[áa]sica", None),
    "outras_multigov": ("1.7", r"Outras Transfer[êe]ncias Multigovernamentais", None),
    "sus":             ("1.7", r"Sistema [ÚU]nico de Sa[úu]de", None),
}

# Transferências não condicionadas (incondicionais) usadas como T no modelo flypaper.
# FUNDEB, SUS, FNDE e convênios ficam de fora por serem vinculados.
INCONDICIONAIS = ["fpm", "itr", "icms_cota", "ipva_cota", "ipi_exp_cota", "iof_ouro"]
ARRECADACAO_PROPRIA_IMPOSTOS = ["iptu", "itbi", "iss"]

_COD = re.compile(r"^\s*(?:RO|DO)?\s*(\d+(?:\.\d+)+)")


def separa_codigo(texto):
    """'1.7.1.8.01.2.0 Cota-Parte...' -> ('1.7.1.8.01.2.0', 'Cota-Parte...')."""
    if not isinstance(texto, str):
        return None, ""
    m = _COD.match(texto)
    if not m:
        return None, texto.strip()
    return m.group(1), texto[m.end():].lstrip(" -–").strip()


def significativo(codigo):
    """Segmentos sem os zeros finais: '1.7.2.1.01.02.00' -> (1,7,2,1,1,2)."""
    seg = [int(x) for x in codigo.split(".")]
    while seg and seg[-1] == 0:
        seg.pop()
    return tuple(seg)


def _topo(cods):
    """Mantém só os códigos que não descendem de outro código da lista."""
    sig = {c: significativo(c) for c in cods}
    out = []
    for c in cods:
        s = sig[c]
        if not any(o != c and len(sig[o]) < len(s) and s[:len(sig[o])] == sig[o] for o in cods):
            out.append(c)
    return out


def extrai(contas):
    """
    contas: DataFrame com colunas 'codigo' (str '1.7.2.1.01.02.00'), 'rotulo' (str) e 'valor' (float),
            de UM município, UM ano e UMA coluna da DCA (ex.: Receitas Brutas Realizadas).
    Retorna dict conceito -> valor (NaN se nenhuma conta casar: ausente ≠ zero) e
            dict conceito -> lista dos códigos usados (para auditoria).
    """
    c = contas.dropna(subset=["codigo"]).drop_duplicates(subset=["codigo"])
    valores, usados = {}, {}
    for nome, (prefixo, rx, rx_exc) in CONCEITOS.items():
        alvo = c[c.codigo.str.startswith(prefixo + ".") | (c.codigo == prefixo)]
        alvo = alvo[alvo.rotulo.str.contains(rx, case=False, regex=True, na=False)]
        if rx_exc:
            alvo = alvo[~alvo.rotulo.str.contains(rx_exc, case=False, regex=True, na=False)]
        if alvo.empty:
            valores[nome], usados[nome] = np.nan, []
            continue
        topo = _topo(list(alvo.codigo))
        sub = alvo[alvo.codigo.isin(topo)]
        valores[nome] = float(pd.to_numeric(sub.valor, errors="coerce").sum(min_count=1))
        usados[nome] = topo
    inc = [valores[k] for k in INCONDICIONAIS]
    # Soma das incondicionais: NaN só se TODAS faltarem (componentes pequenos como IOF-ouro podem não existir)
    valores["transf_incondicionais"] = float(np.nansum(inc)) if not all(np.isnan(inc)) else np.nan
    return valores, usados


def de_dca_api(df_dca):
    """Adapta o formato da API do Siconfi (cod_conta 'RO1.7...', conta '...') para extrai()."""
    out = df_dca.copy()
    cod_rot = out["conta"].apply(separa_codigo)
    out["codigo"] = out["cod_conta"].astype(str).str.replace(r"^(RO|DO)", "", regex=True)
    out.loc[~out["codigo"].str.match(r"^\d+(\.\d+)+$"), "codigo"] = None
    out["rotulo"] = [r for _, r in cod_rot]
    return out[["codigo", "rotulo", "valor"]]
