"""
P2 - Finanças do Setor Público (UnB) - Dados nacionais da Hungria (e Brasil, como referência)
Fonte: World Bank - World Development Indicators (API pública, metadados verificáveis)

Uso (Colab ou local):
    pip install requests pandas
    python coleta_hungria.py

Saídas (data/raw/):
    wdi_hungria_brasil_bruto.csv   -> série longa (país, ano, indicador, valor)
    wdi_metadados_indicadores.csv  -> nome, definição, fonte original e data de atualização
    eurostat_<dataset>_HU.csv      -> Eurostat em formato longo (códigos, rótulos, valor, flag)
    log_coleta_hungria.csv         -> cobertura (anos com dado) por indicador

ATENÇÃO: o WDI traz o governo CENTRAL. Os governos locais húngaros (setor S1313: receita, despesa,
transferências recebidas, impostos, despesa por função) vêm do Eurostat (arquivos eurostat_*_HU.csv). Indicadores sem dados
permanecem vazios (NaN); nenhum valor ausente é trocado por zero.
"""
import os
import time
from datetime import date

import pandas as pd
import requests

OUT = os.path.join("data", "raw")
os.makedirs(OUT, exist_ok=True)

from config import PAIS_ISO3, PAIS_NOME, REFERENCIA_ISO3, EUROSTAT_GEO, USAR_EUROSTAT, ANO_INI, ANO_FIM
PAISES = {PAIS_ISO3: PAIS_NOME, REFERENCIA_ISO3: "Brasil"}
ANOS = f"{ANO_INI - 2}:{ANO_FIM}"

INDICADORES = {
    # Escala e preços
    "NY.GDP.MKTP.CN": "pib_nominal_moeda_local",
    "NY.GDP.MKTP.KN": "pib_real_moeda_local_constante",
    "NY.GDP.PCAP.KN": "pib_per_capita_real_moeda_local",
    "SP.POP.TOTL": "populacao_total",
    "FP.CPI.TOTL": "ipc_indice_2010_100",
    "FP.CPI.TOTL.ZG": "inflacao_ipc_pct_anual",
    "PA.NUS.FCRF": "taxa_cambio_oficial_lcu_por_usd",
    # Governo central (NÃO é nível subnacional)
    "GC.REV.XGRT.GD.ZS": "receita_gov_central_exc_doacoes_pct_pib",
    "GC.TAX.TOTL.GD.ZS": "receita_tributaria_gov_central_pct_pib",
    "GC.XPN.TOTL.GD.ZS": "despesa_gov_central_pct_pib",
    "GC.XPN.TRFT.ZS": "subsidios_e_outras_transf_pct_despesa",
    "GC.XPN.COMP.ZS": "remuneracao_servidores_pct_despesa",
    "NE.CON.GOVT.ZS": "consumo_governo_geral_pct_pib",
    "SE.XPD.TOTL.GD.ZS": "gasto_educacao_pct_pib",
}

log = []


def get_json(url, params=None, tentativas=4):
    ultimo = None
    for i in range(tentativas):
        try:
            r = requests.get(url, params=params, timeout=60)
            if r.status_code == 200:
                return r.json()
            ultimo = f"HTTP {r.status_code}"
        except Exception as e:
            ultimo = repr(e)
        time.sleep(2 * (i + 1))
    raise RuntimeError(ultimo)


def coleta_series():
    linhas = []
    for iso, nome_pais in PAISES.items():
        for cod, nome_var in INDICADORES.items():
            url = f"https://api.worldbank.org/v2/country/{iso}/indicator/{cod}"
            try:
                d = get_json(url, {"format": "json", "date": ANOS, "per_page": 200})
                itens = d[1] if isinstance(d, list) and len(d) > 1 and d[1] else []
                n_ok = 0
                for it in itens:
                    v = it.get("value")
                    linhas.append({"pais_iso3": iso, "pais": nome_pais, "ano": int(it["date"]),
                                   "indicador_codigo": cod, "variavel": nome_var,
                                   "valor": float(v) if v is not None else None})
                    n_ok += v is not None
                log.append({"pais": iso, "indicador": cod, "status": "OK",
                            "anos_com_dado": n_ok, "anos_consultados": len(itens)})
                print(f"[OK] {iso} {cod}: {n_ok}/{len(itens)} anos com dado")
            except Exception as e:
                log.append({"pais": iso, "indicador": cod, "status": f"ERRO {e}",
                            "anos_com_dado": None, "anos_consultados": None})
                print(f"[ERRO] {iso} {cod}: {e}")
    pd.DataFrame(linhas).to_csv(os.path.join(OUT, "wdi_hungria_brasil_bruto.csv"),
                                index=False, encoding="utf-8-sig")


def coleta_metadados():
    meta = []
    for cod in INDICADORES:
        try:
            d = get_json(f"https://api.worldbank.org/v2/indicator/{cod}", {"format": "json"})
            info = d[1][0]
            meta.append({"indicador_codigo": cod, "nome": info.get("name"),
                         "definicao": info.get("sourceNote"),
                         "fonte_base": (info.get("source") or {}).get("value"),
                         "organizacao_fonte": info.get("sourceOrganization"),
                         "ultima_atualizacao_base": d[0].get("lastupdated"),
                         "data_acesso": date.today().isoformat()})
        except Exception as e:
            meta.append({"indicador_codigo": cod, "nome": f"ERRO {e}"})
    pd.DataFrame(meta).to_csv(os.path.join(OUT, "wdi_metadados_indicadores.csv"),
                              index=False, encoding="utf-8-sig")


EUROSTAT = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
# Em vez de adivinhar códigos de item, baixa o recorte inteiro (todas as categorias das dimensões não
# filtradas) e salva em formato longo com códigos E rótulos. O tratamento escolhe as linhas depois.
#   gov_10a_main : receitas/despesas do governo por setor (S13 geral, S1311 central, S1313 local)
#   gov_10a_exp  : despesa por função (COFOG) - comparável à despesa municipal por função
#   gov_10a_taxag: impostos e contribuições por setor
#   prc_hicp_aind: inflação harmonizada (deflator da Hungria)
EUROSTAT_CONSULTAS = {
    "gov_10a_main":  {"sector": ["S13", "S1311", "S1313"], "unit": ["MIO_NAC", "PC_GDP"]},
    "gov_10a_exp":   {"sector": ["S13", "S1313"], "unit": ["MIO_NAC", "PC_GDP"], "na_item": ["TE"]},
    "gov_10a_taxag": {"sector": ["S13", "S1313"], "unit": ["MIO_NAC", "PC_GDP"]},
    "prc_hicp_aind": {"coicop": ["CP00"], "unit": ["INX_A_AVG", "RCH_A_AVG"]},
}


def jsonstat_longo(d):
    """Converte a resposta JSON-stat do Eurostat em linhas (uma por combinação de categorias)."""
    ids, tamanhos = d["id"], d["size"]
    cats = []
    for dim in ids:
        cat = d["dimension"][dim]["category"]
        pos = {v: k for k, v in cat["index"].items()}            # posição -> código
        cats.append((pos, cat.get("label", {})))
    linhas = []
    for chave, v in d.get("value", {}).items():
        resto, idx = int(chave), []
        for t in reversed(tamanhos):                             # índice plano -> posição em cada dimensão
            idx.append(resto % t); resto //= t
        idx.reverse()
        linha = {}
        for dim, (pos, rot), i in zip(ids, cats, idx):
            linha[dim] = pos[i]
            if dim not in ("time", "freq", "geo"):
                linha[f"{dim}_rotulo"] = rot.get(pos[i])
        linha["valor"] = v
        linha["flag"] = (d.get("status") or {}).get(chave)       # p = provisório, e = estimado, b = quebra
        linhas.append(linha)
    return linhas


def coleta_eurostat():
    for ds, filtros in EUROSTAT_CONSULTAS.items():
        params = [("format", "JSON"), ("lang", "EN"), ("geo", EUROSTAT_GEO), ("freq", "A"),
                  ("sinceTimePeriod", str(ANO_INI - 2))]
        for k, vals in filtros.items():
            params += [(k, v) for v in vals]
        try:
            d = get_json(f"{EUROSTAT}/{ds}", params)
            linhas = jsonstat_longo(d)
            df = pd.DataFrame(linhas)
            df.insert(0, "dataset", ds)
            df["atualizado_em"] = d.get("updated")
            df["data_acesso"] = date.today().isoformat()
            df.to_csv(os.path.join(OUT, f"eurostat_{ds}_HU.csv"), index=False, encoding="utf-8-sig")
            anos = sorted(df["time"].unique()) if len(df) else []
            log.append({"pais": EUROSTAT_GEO, "indicador": f"Eurostat {ds}", "status": "OK",
                        "anos_com_dado": f"{anos[0]}-{anos[-1]}" if anos else 0, "anos_consultados": len(df)})
            print(f"[OK] Eurostat {ds}: {len(df)} valores, anos {anos[:1]}...{anos[-1:]}")
        except Exception as e:
            log.append({"pais": EUROSTAT_GEO, "indicador": f"Eurostat {ds}", "status": f"ERRO {e}",
                        "anos_com_dado": None, "anos_consultados": None})
            print(f"[ERRO] Eurostat {ds}: {e}")


if __name__ == "__main__":
    coleta_series()
    if USAR_EUROSTAT:
        coleta_eurostat()
    coleta_metadados()
    pd.DataFrame(log).to_csv(os.path.join(OUT, "log_coleta_hungria.csv"),
                             index=False, encoding="utf-8-sig")
    print("\nConcluído. Veja data/raw/log_coleta_hungria.csv (cobertura por indicador).")
