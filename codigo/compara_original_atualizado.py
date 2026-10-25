"""
Registro de alterações: compara a base da P1 (data/original/painel_original.csv, gerada por
importa_base_original.py) com o painel tratado da P2 (data/tratados/tratado_municipios.csv),
ano a ano, nos anos em comum (2014-2023), em VALORES NOMINAIS (mesma unidade da P1).

Saídas (data/registro_alteracoes/):
  comparacao_P1_P2.csv   uma linha por município × ano × variável: valor P1, valor P2, diferença e motivo
  resumo_alteracoes.csv  contagem por variável e tipo de alteração
Uso: python codigo/compara_original_atualizado.py
"""
import os
import numpy as np
import pandas as pd

OUT = os.path.join("data", "registro_alteracoes")
os.makedirs(OUT, exist_ok=True)

# variável da P1 -> (variável da P2, fator para levar a P1 à unidade da P2)
MAPA = {
    "Receita_Total": ("rec_total", 1), "Receita_Tributaria": ("rec_tributaria", 1),
    "IPTU": ("rec_iptu", 1), "ISS": ("rec_iss", 1), "ITBI": ("rec_itbi", 1),
    "Transferencias": ("rec_transf_correntes", 1), "FPM": ("rec_fpm", 1), "ICMS": ("rec_icms_cota", 1),
    "FUNDEB": ("rec_fundeb", 1), "Despesa_Total": ("desp_total", 1), "Despesas_Correntes": ("desp_corrente", 1),
    "Pessoal_Encargos": ("desp_pessoal", 1), "Despesas_Capital": ("desp_capital", 1),
    "Funcao_Educacao": ("desp_educacao", 1), "Funcao_Saude": ("desp_saude", 1),
    "População": ("populacao", 1), "PIB": ("pib_nominal", 1000),   # P1: PIB em R$ mil
}
TOL = 1e-3   # diferença relativa abaixo de 0,1% = igual (arredondamento)


def motivo(var_p1, mun, ano, v1, v2, dca):
    if pd.isna(v1) and pd.notna(v2):
        if var_p1 == "População":
            return "PREENCHIDO", "P1 sem valor; P2 usa Censo 2022 (2022) e interpolação linear Censo 2022-estimativa 2024 (2023)"
        return "PREENCHIDO", "P1 sem valor; P2 coletou na fonte"
    if pd.notna(v1) and v1 == 0 and pd.notna(v2) and v2 > 0:
        return "CORRIGIDO", "P1 gravou zero (função ausente na aba bruta); P2 traz o valor da DCA, Anexo I-E"
    if var_p1 == "FPM":
        return "CORRIGIDO", "P1 contou só a cota mensal; P2 soma também as parcelas de 1% (mesma definição em todos os anos)"
    if var_p1 == "Receita_Total" and dca is not None:
        intra = dca.get((mun, ano))
        if intra and abs((v2 - v1) - intra) / intra < TOL:
            return "CORRIGIDO", (f"P1 usou receita exceto intra-orçamentárias (R$ {intra:,.2f} a menos), mas despesa total "
                                 "com intra; P2 usa o total com intra nas duas, mantendo o resultado consistente")
    if var_p1 == "População":
        return "CORRIGIDO", "Valor da P1 diverge da estimativa oficial do IBGE (SIDRA 6579); provável erro de digitação na P1"
    return "A INVESTIGAR", ""


def intra_orcamentarias():
    """Receita intra-orçamentária por município e ano (para explicar diferenças da receita total)."""
    f = os.path.join("data", "raw", "siconfi_dca_bruto.csv")
    if not os.path.exists(f):
        return None
    d = pd.read_csv(f, low_memory=False)
    d = d[(d.anexo == "DCA-Anexo I-C") & (d.coluna == "Receitas Brutas Realizadas")
          & (d.cod_conta == "ReceitasIntraOrcamentarias")]
    return {(m, int(a)): float(v) for m, a, v in zip(d.municipio, d.exercicio, d.valor)}


def main():
    p1 = pd.read_csv(os.path.join("data", "original", "painel_original.csv"))
    p2 = pd.read_csv(os.path.join("data", "tratados", "tratado_municipios.csv"))
    dca = intra_orcamentarias()
    x = p1.merge(p2, on=["municipio", "ano"], how="inner")
    x = x[x.ano <= 2023]                     # anos cobertos pela P1 (2024 na P1 só tem população)
    linhas = []
    for var_p1, (var_p2, fator) in MAPA.items():
        for _, r in x.iterrows():
            v1 = r[var_p1] * fator if pd.notna(r[var_p1]) else np.nan
            v2 = r[var_p2]
            if pd.isna(v1) and pd.isna(v2):
                tipo, mot = "AUSENTE NAS DUAS", "sem dado na fonte"
            elif pd.notna(v1) and pd.notna(v2) and v1 != 0 and abs(v2 - v1) / abs(v1) < TOL:
                tipo, mot = "IGUAL", ""
            else:
                tipo, mot = motivo(var_p1, r.municipio, r.ano, v1, v2, dca)
            linhas.append({"municipio": r.municipio, "ano": int(r.ano), "variavel_P1": var_p1, "variavel_P2": var_p2,
                           "valor_P1": v1, "valor_P2": v2,
                           "dif_abs": v2 - v1 if pd.notna(v1) and pd.notna(v2) else np.nan,
                           "dif_rel": (v2 - v1) / v1 if pd.notna(v1) and pd.notna(v2) and v1 else np.nan,
                           "tipo": tipo, "motivo": mot})
    c = pd.DataFrame(linhas)
    c.to_csv(os.path.join(OUT, "comparacao_P1_P2.csv"), index=False, encoding="utf-8-sig")
    resumo = c.pivot_table(index="variavel_P1", columns="tipo", values="ano", aggfunc="count", fill_value=0)
    resumo.to_csv(os.path.join(OUT, "resumo_alteracoes.csv"), encoding="utf-8-sig")
    print(resumo)
    print("\nAlterações (exceto IGUAL):")
    print(c[c.tipo != "IGUAL"][["municipio", "ano", "variavel_P1", "valor_P1", "valor_P2", "dif_rel", "tipo"]]
          .to_string(index=False))


if __name__ == "__main__":
    main()
