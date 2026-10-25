"""
Configuração única do projeto P2. Para trocar de caso (municípios/país), edite SÓ este arquivo.

Municípios (código IBGE de 7 dígitos). O script de coleta VALIDA o nome pelo IBGE antes de baixar;
se algum código estiver errado, ele para e avisa.
"""
MUNICIPIOS = {
    2903201: "Barreiras",   # BA
    2905701: "Camaçari",    # BA
}
UF_ESPERADA = {2903201: "BA", 2905701: "BA"}

# País do caso atribuído (ISO3) e referência (Brasil)
PAIS_ISO3 = "HUN"
PAIS_NOME = "Hungria"
REFERENCIA_ISO3 = "BRA"
EUROSTAT_GEO = "HU"            # para países da UE; deixe None se não houver dados Eurostat
USAR_EUROSTAT = True

# Período e deflator
ANO_INI, ANO_FIM = 2014, 2025   # coleta 2014-2025: sobrepõe a P1 (2014-2023) para o registro de alterações.
JANELA_ANALISE = (2016, 2025)   # 10 anos mais recentes com DCA completa (conferir 2025 no log). PIB municipal só até 2023.
ANO_BASE = 2025                 # preços constantes de 2025 (IPCA média anual)

# População do Censo 2022 (usada onde a tabela 6579 do IBGE não traz 2022).
# O coleta_municipios.py baixa da tabela 4714 do SIDRA. Se falhar, preencha data/manual/censo2022.csv
# (colunas: cod_ibge,populacao) com o valor oficial do IBGE.
