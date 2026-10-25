"""
P2 - Tratamento dos dados da Hungria (governos locais e governo geral) e do Brasil (referência)
Entrada : data/raw/eurostat_*_HU.csv e data/raw/wdi_hungria_brasil_bruto.csv (coleta_hungria.py)
Saída   : data/tratados/tratado_hungria.csv          painel anual (uma linha por ano)
          data/tratados/hungria_cofog_local.csv      despesa local por função (COFOG), % do PIB
          data/registro_alteracoes/hungria_P1_P2.csv comparação com a planilha da P1 (governo geral)

Definições (Eurostat, SEC 2010; setores S13 = governo geral, S1311 = central, S1313 = local):
  receita/despesa total              TR / TE
  transferências correntes recebidas D73REC  (transferências correntes dentro do governo geral)
  transferências de capital          D9REC   (inclui fundos da UE repassados)
  impostos locais                    D2REC + D5REC + D91REC
  deflator                           HICP médio anual (prc_hicp_aind, 2015=100), rebaseado para ANO_BASE
  população                          Banco Mundial, SP.POP.TOTL
Ausente permanece NaN. Valores monetários em milhões de HUF (MIO_NAC).
"""
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import ANO_BASE  # noqa: E402

RAW = os.path.join("data", "raw")
OUT = os.path.join("data", "tratados")
REG = os.path.join("data", "registro_alteracoes")
os.makedirs(OUT, exist_ok=True); os.makedirs(REG, exist_ok=True)


def serie(m, setor, item, unidade):
    s = m[(m.sector == setor) & (m.na_item == item) & (m.unit == unidade)].set_index("time")["valor"]
    return s.astype(float)


def main():
    m = pd.read_csv(os.path.join(RAW, "eurostat_gov_10a_main_HU.csv"))
    anos = sorted(m.time.unique())
    df = pd.DataFrame(index=pd.Index(anos, name="ano"))

    for setor, pre in [("S1313", "loc"), ("S13", "gg"), ("S1311", "cen")]:
        for item, nome in [("TR", "receita"), ("TE", "despesa"), ("B9", "saldo")]:
            df[f"{pre}_{nome}_mio_huf"] = serie(m, setor, item, "MIO_NAC")
            df[f"{pre}_{nome}_pct_pib"] = serie(m, setor, item, "PC_GDP")
    df["loc_transf_correntes_mio_huf"] = serie(m, "S1313", "D73REC", "MIO_NAC")
    df["loc_transf_capital_mio_huf"] = serie(m, "S1313", "D9REC", "MIO_NAC")
    df["loc_impostos_mio_huf"] = sum(serie(m, "S1313", i, "MIO_NAC") for i in ["D2REC", "D5REC", "D91REC"])
    df["loc_transf_correntes_pct_pib"] = serie(m, "S1313", "D73REC", "PC_GDP")
    df["loc_impostos_pct_pib"] = sum(serie(m, "S1313", i, "PC_GDP") for i in ["D2REC", "D5REC", "D91REC"])

    # Razões (sem unidade): comparáveis às dos municípios brasileiros
    df["loc_transf_correntes_sobre_receita"] = df.loc_transf_correntes_mio_huf / df.loc_receita_mio_huf
    df["loc_transf_total_sobre_receita"] = (df.loc_transf_correntes_mio_huf + df.loc_transf_capital_mio_huf) / df.loc_receita_mio_huf
    df["loc_impostos_sobre_receita"] = df.loc_impostos_mio_huf / df.loc_receita_mio_huf
    df["loc_despesa_sobre_despesa_gg"] = df.loc_despesa_mio_huf / df.gg_despesa_mio_huf   # grau de descentralização

    # Deflator (HICP) e per capita
    h = pd.read_csv(os.path.join(RAW, "eurostat_prc_hicp_aind_HU.csv"))
    hicp = h[h.unit == "INX_A_AVG"].set_index("time")["valor"].astype(float)
    df["hicp_2015_100"] = hicp
    df["fator_deflator"] = hicp.get(ANO_BASE, np.nan) / df["hicp_2015_100"]
    w = pd.read_csv(os.path.join(RAW, "wdi_hungria_brasil_bruto.csv"))
    hun = w[w.pais_iso3 == "HUN"].pivot_table(index="ano", columns="indicador_codigo", values="valor")
    df["populacao"] = hun.get("SP.POP.TOTL")
    df["pib_mio_huf_wdi"] = hun.get("NY.GDP.MKTP.CN") / 1e6
    for c in ["loc_receita", "loc_despesa", "loc_transf_correntes", "loc_impostos"]:
        df[f"{c}_huf_real_pc"] = df[f"{c}_mio_huf"] * 1e6 * df["fator_deflator"] / df["populacao"]
    df["ano_base_preco"] = ANO_BASE
    df.reset_index().to_csv(os.path.join(OUT, "tratado_hungria.csv"), index=False, encoding="utf-8-sig")

    # Despesa local por função (COFOG, 1º nível), % do PIB e % da despesa local
    e = pd.read_csv(os.path.join(RAW, "eurostat_gov_10a_exp_HU.csv"))
    e = e[(e.sector == "S1313") & (e.na_item == "TE") & e.cofog99.str.match(r"^GF\d\d$")]
    cof = e.pivot_table(index=["cofog99", "cofog99_rotulo"], columns=["unit", "time"], values="valor")
    cof.to_csv(os.path.join(OUT, "hungria_cofog_local.csv"), encoding="utf-8-sig")

    # Comparação com a P1 (planilha Hungria_2014_2023.xlsx: governo geral, HUF bilhões; 2014-2021 estimados)
    p1 = {"Receita Total (HUF bilhões)": [15581, 15735, 16155, 17060, 18861, 21054, 22310, 24608, 28145, 32111],
          "Despesa Total (HUF bilhões)": [16486, 16383, 16766, 17864, 19705, 21866, 25932, 28526, 32271, 37146]}
    comp = []
    for i, ano in enumerate(range(2014, 2024)):
        for var, col in [("Receita Total (HUF bilhões)", "gg_receita_mio_huf"), ("Despesa Total (HUF bilhões)", "gg_despesa_mio_huf")]:
            v1, v2 = p1[var][i], df.loc[ano, col] / 1000
            comp.append({"ano": ano, "variavel_P1": var, "valor_P1": v1, "valor_P2_eurostat": round(v2, 1),
                         "dif_rel": (v2 - v1) / v1,
                         "motivo": ("P1: estimativa (% do PIB × PIB estimado)" if ano <= 2021 else "P1: KSH/EDP")
                                   + "; P2: Eurostat gov_10a_main, valor oficial em MIO_NAC"})
    pd.DataFrame(comp).to_csv(os.path.join(REG, "hungria_P1_P2.csv"), index=False, encoding="utf-8-sig")

    cols = ["loc_receita_pct_pib", "loc_despesa_pct_pib", "loc_transf_correntes_sobre_receita",
            "loc_impostos_sobre_receita", "loc_despesa_sobre_despesa_gg", "loc_despesa_huf_real_pc"]
    print(df[cols].round(3).to_string())
    print(pd.DataFrame(comp).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
