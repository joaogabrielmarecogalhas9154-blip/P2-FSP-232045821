"""
Gera o dicionário de variáveis (docs/dicionario_variaveis.csv e .md) a partir das definições abaixo
e da cobertura observada nos dados tratados (anos com valor por unidade). Rodar depois do tratamento.
Uso: python codigo/gera_dicionario.py
"""
import os
import pandas as pd

SIC = "Siconfi/DCA - https://apidatalake.tesouro.gov.br/ords/siconfi/tt/dca"
SID = "IBGE/SIDRA - https://sidra.ibge.gov.br/tabela/{}"
EUR = "Eurostat - https://ec.europa.eu/eurostat/databrowser/view/{}/default/table"
WB = "Banco Mundial (WDI) - https://data.worldbank.org/indicator/{}"
AUS = "Ausente permanece vazio (NaN); nunca substituído por zero"
RB = "DCA Anexo I-C, coluna 'Receitas Brutas Realizadas'"
DE = "DCA, coluna 'Despesas Empenhadas'"

# nome: (definição, fonte, unidade, transformação/fórmula)
MUN = {
    "rec_total": ("Receita orçamentária total, incluindo intra-orçamentárias (linha 'TotalReceitas')", SIC, "R$ correntes", RB),
    "rec_corrente": ("Receitas correntes (natureza 1.0.0.0)", SIC, "R$ correntes", RB),
    "rec_tributaria": ("Impostos, taxas e contribuições de melhoria (natureza 1.1)", SIC, "R$ correntes", RB),
    "rec_transf_correntes": ("Transferências correntes (natureza 1.7)", SIC, "R$ correntes", RB),
    "rec_transf_uniao": ("Transferências correntes da União (1.7.2.1 até 2017; 1.7.1 a partir de 2018)", SIC, "R$ correntes", RB + "; mapeamento dependente do ano (quebra de 2018)"),
    "rec_transf_estados": ("Transferências correntes do Estado (1.7.2.2 até 2017; 1.7.2 a partir de 2018)", SIC, "R$ correntes", RB + "; mapeamento dependente do ano"),
    "rec_iptu": ("IPTU", SIC, "R$ correntes", RB + "; conta identificada por código + rótulo (rubricas_receita.py); a partir de 2018 inclui multas e dívida ativa do imposto"),
    "rec_itbi": ("ITBI", SIC, "R$ correntes", RB + "; código + rótulo"),
    "rec_iss": ("ISS/ISSQN", SIC, "R$ correntes", RB + "; código + rótulo"),
    "rec_fpm": ("Cota-parte do FPM, incluindo as parcelas adicionais de 1% (julho, setembro, dezembro)", SIC, "R$ correntes", RB + "; soma das contas de nível mais alto que casam com o rótulo"),
    "rec_itr": ("Cota-parte do ITR", SIC, "R$ correntes", RB),
    "rec_icms_cota": ("Cota-parte do ICMS (exclui a desoneração da LC 87/96)", SIC, "R$ correntes", RB),
    "rec_ipva_cota": ("Cota-parte do IPVA", SIC, "R$ correntes", RB),
    "rec_ipi_exp_cota": ("Cota-parte do IPI-exportação", SIC, "R$ correntes", RB),
    "rec_iof_ouro": ("Cota-parte do IOF-ouro", SIC, "R$ correntes", RB + "; sem lançamento nos dois municípios (vazio)"),
    "rec_fundeb": ("Transferências do FUNDEB, incluindo a complementação da União (bruto, antes da dedução)", SIC, "R$ correntes", RB),
    "rec_outras_multigov": ("Outras transferências multigovernamentais (extraordinárias; Barreiras 2017)", SIC, "R$ correntes", RB),
    "rec_sus": ("Transferências do SUS (União e Estado)", SIC, "R$ correntes", RB),
    "rec_transf_incondicionais": ("Transferências incondicionais: FPM + ITR + cotas de ICMS, IPVA e IPI-exportação + IOF-ouro", SIC, "R$ correntes", "Soma; vazio só se todos os componentes faltarem"),
    "ded_fundeb_corrente": ("Dedução para formação do FUNDEB sobre as receitas correntes", SIC, "R$ correntes", "DCA Anexo I-C, coluna 'Deduções - FUNDEB'"),
    "ded_fundeb_total": ("Dedução para o FUNDEB sobre a receita total", SIC, "R$ correntes", "DCA Anexo I-C, coluna 'Deduções - FUNDEB'"),
    "desp_total": ("Despesa total empenhada (Total Geral da Despesa, com intra-orçamentárias)", SIC, "R$ correntes", "DCA Anexo I-D, " + DE),
    "desp_corrente": ("Despesas correntes (3.0)", SIC, "R$ correntes", "DCA Anexo I-D, " + DE),
    "desp_pessoal": ("Pessoal e encargos sociais (3.1)", SIC, "R$ correntes", "DCA Anexo I-D, " + DE),
    "desp_capital": ("Despesas de capital (4.0)", SIC, "R$ correntes", "DCA Anexo I-D, " + DE),
    "desp_educacao": ("Despesa na função 12 - Educação", SIC, "R$ correntes", "DCA Anexo I-E, " + DE),
    "desp_saude": ("Despesa na função 10 - Saúde", SIC, "R$ correntes", "DCA Anexo I-E, " + DE),
    "populacao": ("População residente", SID.format("6579") + "; Censo 2022: " + SID.format("4714"), "pessoas",
                  "Estimativas do IBGE; 2022 = Censo; 2023 = interpolação linear Censo 2022-estimativa 2024 (coluna pop_fonte)"),
    "pib_nominal": ("PIB municipal a preços correntes", SID.format("5938"), "R$ correntes", "Tabela 5938 (R$ mil) × 1.000; disponível até 2023"),
    "vab_agro": ("Valor adicionado bruto da agropecuária", SID.format("5938"), "R$ correntes", "× 1.000"),
    "vab_industria": ("Valor adicionado bruto da indústria", SID.format("5938"), "R$ correntes", "× 1.000"),
    "vab_servicos": ("Valor adicionado bruto dos serviços (exceto adm. pública)", SID.format("5938"), "R$ correntes", "× 1.000"),
    "vab_adm_publica": ("Valor adicionado bruto da administração pública", SID.format("5938"), "R$ correntes", "× 1.000"),
    "ipca_media_anual": ("IPCA, número-índice (dez/1993 = 100), média dos 12 meses do ano", SID.format("1737"), "índice", "Média aritmética mensal"),
    "fator_deflator": ("Fator para converter valores do ano t a preços de 2025", SID.format("1737"), "razão", "IPCA_médio(2025) / IPCA_médio(t)"),
    "impostos_proprios": ("IPTU + ISS + ITBI", SIC, "R$ correntes", "Soma; vazio se algum componente faltar"),
    "transf_sobre_rec_corrente": ("Transferências correntes / receita corrente", SIC, "razão", "rec_transf_correntes / rec_corrente (nominais do mesmo ano)"),
    "tributaria_sobre_rec_corrente": ("Receita tributária / receita corrente", SIC, "razão", "rec_tributaria / rec_corrente"),
    "transf_incond_sobre_rec_corrente": ("Transferências incondicionais / receita corrente", SIC, "razão", "rec_transf_incondicionais / rec_corrente"),
    "rec_corrente_sem_extraord": ("Receita corrente sem as transferências extraordinárias", SIC, "R$ correntes", "rec_corrente - rec_outras_multigov"),
    "rec_total_liq_fundeb": ("Receita total líquida da dedução do FUNDEB", SIC, "R$ correntes", "rec_total - ded_fundeb_total"),
    "resultado_orcamentario": ("Resultado orçamentário", SIC, "R$ correntes", "rec_total_liq_fundeb - desp_total"),
    "resultado_bruto_sem_deducao": ("Resultado sem descontar o FUNDEB (definição da P1, para comparação)", SIC, "R$ correntes", "rec_total - desp_total"),
    "dummy_pos2018": ("1 a partir de 2018 (nova classificação da receita)", "construída", "0/1", "ano >= 2018"),
}
HUN = {
    "loc_receita_mio_huf": ("Receita total dos governos locais (S1313, TR)", EUR.format("gov_10a_main"), "milhões de HUF correntes", "Valor oficial"),
    "loc_despesa_mio_huf": ("Despesa total dos governos locais (S1313, TE)", EUR.format("gov_10a_main"), "milhões de HUF correntes", "Valor oficial"),
    "loc_receita_pct_pib": ("Receita dos governos locais em % do PIB", EUR.format("gov_10a_main"), "% do PIB", "Unidade PC_GDP do Eurostat"),
    "loc_despesa_pct_pib": ("Despesa dos governos locais em % do PIB", EUR.format("gov_10a_main"), "% do PIB", "Unidade PC_GDP"),
    "loc_transf_correntes_mio_huf": ("Transferências correntes recebidas de dentro do governo geral (D73REC)", EUR.format("gov_10a_main"), "milhões de HUF", "Valor oficial"),
    "loc_transf_capital_mio_huf": ("Transferências de capital recebidas (D9REC; inclui fundos da UE)", EUR.format("gov_10a_main"), "milhões de HUF", "Valor oficial"),
    "loc_impostos_mio_huf": ("Impostos dos governos locais (D2REC + D5REC + D91REC)", EUR.format("gov_10a_main"), "milhões de HUF", "Soma"),
    "loc_transf_correntes_sobre_receita": ("Transferências correntes / receita local", EUR.format("gov_10a_main"), "razão", "D73REC / TR"),
    "loc_transf_total_sobre_receita": ("Transferências correntes e de capital / receita local", EUR.format("gov_10a_main"), "razão", "(D73REC + D9REC) / TR"),
    "loc_impostos_sobre_receita": ("Impostos locais / receita local", EUR.format("gov_10a_main"), "razão", "(D2 + D5 + D91) / TR"),
    "loc_despesa_sobre_despesa_gg": ("Despesa local / despesa do governo geral (grau de descentralização)", EUR.format("gov_10a_main"), "razão", "TE(S1313) / TE(S13)"),
    "gg_receita_mio_huf": ("Receita total do governo geral (S13)", EUR.format("gov_10a_main"), "milhões de HUF", "Valor oficial"),
    "gg_despesa_mio_huf": ("Despesa total do governo geral (S13)", EUR.format("gov_10a_main"), "milhões de HUF", "Valor oficial"),
    "hicp_2015_100": ("Índice harmonizado de preços ao consumidor, média anual", EUR.format("prc_hicp_aind"), "índice (2015 = 100)", "Unidade INX_A_AVG"),
    "fator_deflator": ("Fator para preços de 2025 (Hungria)", EUR.format("prc_hicp_aind"), "razão", "HICP(2025) / HICP(t)"),
    "populacao": ("População total da Hungria", WB.format("SP.POP.TOTL"), "pessoas", "Valor original"),
    "loc_despesa_huf_real_pc": ("Despesa local real per capita", "Eurostat + Banco Mundial", "HUF de 2025 por habitante", "loc_despesa_mio_huf × 10^6 × fator_deflator / populacao"),
}


def cobertura(df, col, por):
    if col not in df.columns:
        return "não gerada"
    partes = []
    for u, g in df.groupby(por) if por else [("Hungria", df)]:
        anos = g.loc[g[col].notna(), "ano"].astype(int)
        partes.append(f"{u}: {anos.min()}-{anos.max()} ({len(anos)} anos)" if len(anos) else f"{u}: sem dados")
    return "; ".join(partes)


def main():
    tm = pd.read_csv(os.path.join("data", "tratados", "tratado_municipios.csv"))
    th = pd.read_csv(os.path.join("data", "tratados", "tratado_hungria.csv"))
    linhas = []
    for nome, (dfn, fonte, un, tr) in MUN.items():
        linhas.append({"base": "tratado_municipios.csv", "variavel": nome, "definicao": dfn, "fonte": fonte, "unidade": un,
                       "cobertura": cobertura(tm, nome, "municipio"), "ausentes": AUS, "transformacao": tr})
    linhas.append({"base": "tratado_municipios.csv", "variavel": "<var>_real", "definicao": "Valor real da variável monetária",
                   "fonte": "derivada", "unidade": "R$ de 2025", "cobertura": "igual à da variável original", "ausentes": AUS,
                   "transformacao": "<var> × fator_deflator"})
    linhas.append({"base": "tratado_municipios.csv", "variavel": "<var>_real_pc", "definicao": "Valor real per capita",
                   "fonte": "derivada", "unidade": "R$ de 2025 por habitante", "cobertura": "igual à da variável original",
                   "ausentes": AUS, "transformacao": "<var>_real / populacao"})
    for nome, (dfn, fonte, un, tr) in HUN.items():
        linhas.append({"base": "tratado_hungria.csv", "variavel": nome, "definicao": dfn, "fonte": fonte, "unidade": un,
                       "cobertura": cobertura(th, nome, None), "ausentes": AUS, "transformacao": tr})
    d = pd.DataFrame(linhas)
    os.makedirs("docs", exist_ok=True)
    d.to_csv(os.path.join("docs", "dicionario_variaveis.csv"), index=False, encoding="utf-8-sig")
    with open(os.path.join("docs", "dicionario_variaveis.md"), "w", encoding="utf-8") as f:
        f.write("# Dicionário de variáveis\n\nGerado por `codigo/gera_dicionario.py`. Valores ausentes: " + AUS +
                ".\nPreços constantes de 2025 (Brasil: IPCA médio anual; Hungria: HICP médio anual).\n\n")
        for base, g in d.groupby("base", sort=False):
            f.write(f"## {base}\n\n| Variável | Definição | Fonte | Unidade | Cobertura | Transformação |\n|---|---|---|---|---|---|\n")
            for _, r in g.iterrows():
                f.write(f"| `{r.variavel}` | {r.definicao} | {r.fonte} | {r.unidade} | {r.cobertura} | {r.transformacao} |\n")
            f.write("\n")
    print(len(d), "variáveis documentadas")


if __name__ == "__main__":
    main()
