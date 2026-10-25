"""
P2 - Finanças do Setor Público (UnB) - Coleta de dados brutos dos municípios
Municípios: definidos em config.py (Barreiras/BA e Camaçari/BA)

Uso:
    pip install requests pandas
    python coleta_municipios.py

Saídas (pasta data/raw/):
    siconfi_dca_bruto.csv    -> DCA completa (todos os anexos) por município e ano
    sidra_pib_municipal.csv  -> Tabela 5938 (PIB dos Municípios)
    sidra_populacao.csv      -> Tabela 6579 (estimativas de população)
    sidra_ipca_indice.csv    -> Tabela 1737 (IPCA, número-índice)
    log_coleta.csv           -> o que foi coletado ou falhou (documenta dados ausentes)

IMPORTANTE: não alterar os valores brutos. Tratamentos (deflação, per capita,
agregação por rubrica) devem ser feitos em outro script, em data/tratados/.
Nenhum valor ausente é substituído por zero.
"""
import os
import time
from datetime import datetime

import pandas as pd
import requests

from config import MUNICIPIOS, UF_ESPERADA, ANO_INI, ANO_FIM
ANOS = list(range(ANO_INI, ANO_FIM + 1))  # confira até qual ano a DCA está completa
SICONFI = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/dca"
SIDRA = "https://apisidra.ibge.gov.br/values"
OUT = os.path.join("data", "raw")
os.makedirs(OUT, exist_ok=True)

log = []


def registrar(fonte, detalhe, status, n=None):
    log.append({"data_hora": datetime.now().isoformat(timespec="seconds"),
                "fonte": fonte, "detalhe": detalhe, "status": status, "linhas": n})
    print(f"[{status}] {fonte} | {detalhe} | {n if n is not None else ''}")


def get_json(url, params=None, tentativas=4):
    for i in range(tentativas):
        try:
            r = requests.get(url, params=params, timeout=90)
            if r.status_code == 200:
                return r.json()
            erro = f"HTTP {r.status_code}"
        except Exception as e:  # rede, timeout, JSON inválido
            erro = repr(e)
        time.sleep(2 * (i + 1))
    raise RuntimeError(erro)


# ---------------------------------------------------------------- validação IBGE
def valida_municipios():
    """Aborta se o código IBGE não corresponder ao nome/UF esperados (evita coletar o município errado)."""
    for cod, nome in MUNICIPIOS.items():
        d = get_json(f"https://servicodados.ibge.gov.br/api/v1/localidades/municipios/{cod}")
        d = d[0] if isinstance(d, list) else d
        nome_ibge = d["nome"]
        try:
            uf = d["microrregiao"]["mesorregiao"]["UF"]["sigla"]
        except (KeyError, TypeError):
            uf = d["regiao-imediata"]["regiao-intermediaria"]["UF"]["sigla"]
        ok = nome_ibge == nome and uf == UF_ESPERADA[cod]
        registrar("IBGE localidades", f"{cod} -> {nome_ibge}/{uf}", "OK" if ok else "DIVERGENTE")
        if not ok:
            raise SystemExit(f"Código {cod} é {nome_ibge}/{uf}, esperado {nome}/{UF_ESPERADA[cod]}. Corrija config.py.")


# ---------------------------------------------------------------- Siconfi DCA
def coleta_dca():
    frames = []
    for ente, nome in MUNICIPIOS.items():
        for ano in ANOS:
            itens, offset = [], 0
            try:
                while True:
                    d = get_json(SICONFI, {"an_exercicio": ano, "id_ente": ente,
                                           "offset": offset})
                    itens += d.get("items", [])
                    if not d.get("hasMore"):
                        break
                    offset += d.get("limit", len(d.get("items", []))) or 0
                    time.sleep(1)  # a API do Siconfi limita a frequência de requisições
                if itens:
                    df = pd.DataFrame(itens)
                    df["municipio"] = nome
                    frames.append(df)
                    registrar("Siconfi DCA", f"{nome} {ano}", "OK", len(df))
                else:
                    registrar("Siconfi DCA", f"{nome} {ano}", "SEM DADOS (não entregue ou não publicado)", 0)
            except Exception as e:
                registrar("Siconfi DCA", f"{nome} {ano}", f"ERRO {e}")
            time.sleep(1)  # pausa entre anos (limite de requisições do Siconfi)
    if frames:
        pd.concat(frames, ignore_index=True).to_csv(
            os.path.join(OUT, "siconfi_dca_bruto.csv"), index=False, encoding="utf-8-sig")


# ---------------------------------------------------------------- IBGE SIDRA
def sidra(tabela, caminho, arquivo, descricao):
    url = f"{SIDRA}{caminho}"
    try:
        d = get_json(url)
        df = pd.DataFrame(d[1:])           # a linha 0 é o cabeçalho descritivo
        df.columns = [d[0].get(c, c) for c in df.columns]
        # Mantém o valor original ("V") e cria coluna numérica; '...', '-', 'X' viram NaN, nunca 0
        if "Valor" in df.columns:
            df["valor_num"] = pd.to_numeric(df["Valor"], errors="coerce")
        df.to_csv(os.path.join(OUT, arquivo), index=False, encoding="utf-8-sig")
        registrar("IBGE SIDRA", f"{descricao} (tabela {tabela})", "OK", len(df))
    except Exception as e:
        registrar("IBGE SIDRA", f"{descricao} (tabela {tabela})", f"ERRO {e}")


def coleta_ibge():
    cods = ",".join(str(c) for c in MUNICIPIOS)
    # PIB municipal: todas as variáveis, todos os períodos disponíveis
    sidra(5938, f"/t/5938/n6/{cods}/v/all/p/all", "sidra_pib_municipal.csv", "PIB dos Municípios")
    # População estimada (série 2001-). Para 2022 existe também o Censo (tabela 4709)
    sidra(6579, f"/t/6579/n6/{cods}/v/all/p/all", "sidra_populacao.csv", "Estimativas de população")
    # Censo 2022 (população residente) - usado onde a tab. 6579 não traz 2022
    sidra(4714, f"/t/4714/n6/{cods}/v/93/p/2022", "sidra_censo2022.csv", "Censo 2022 população")
    # IPCA número-índice (dez/1993=100), Brasil, mensal - base para o deflator
    sidra(1737, "/t/1737/n1/all/v/2266/p/all", "sidra_ipca_indice.csv", "IPCA número-índice")


if __name__ == "__main__":
    valida_municipios()
    coleta_dca()
    coleta_ibge()
    pd.DataFrame(log).to_csv(os.path.join(OUT, "log_coleta.csv"), index=False, encoding="utf-8-sig")
    print("\nConcluído. Veja data/raw/log_coleta.csv")
