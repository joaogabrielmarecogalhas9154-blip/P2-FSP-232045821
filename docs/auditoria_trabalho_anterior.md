# Auditoria do trabalho anterior (P1): base para o registro de alterações

**Trabalho anterior:** João Paulo Cortes da Cunha Dutra (241021838), *P1 – Finanças e Setor Público: Análise Fiscal Comparada – Hungria, Camaçari/BA e Barreiras/BA*, 2026/1.
**Repositório:** https://github.com/Jhons777/P1-Finan-as-do-Setor-Publico---Jo-o-Paulo-Cortes-Da-Cunha-Dutra-241021838
**Versão auditada:** commit `4ae3ff41d0895097b752359aad152a4cac551f33` (08/05/2026).
**Cópia preservada:** `data/original/P1_anterior/`, sem nenhuma alteração.
**Reprodução:** `python codigo/importa_base_original.py data/original/P1_anterior` gera `contas_receita_original.csv`, `painel_original.csv`, `validacao_extrator.csv` e `achados_auditoria.csv` em `data/original/`.

## 1. O que a P1 contém

| Bloco | Arquivo na P1 | Fonte declarada | Período | Observação |
|---|---|---|---|---|
| Receitas | `Dados Brutos/Receitas orçamentarias/Base_receitas (Principal).xlsx` | Siconfi/Finbra, DCA Anexo I-C | 2014–2023 | 10 variáveis; uma aba bruta por município e ano |
| Despesas por natureza | `Dados Brutos/Despesas orçamentarias/base_despesas (principal).xlsx` | DCA Anexo I-D, empenhadas | 2014–2023 | 9 variáveis |
| Despesas por função | `Dados Brutos/Despesas por função/base_despesas_funcao_2014_2023.xlsx` | DCA Anexo I-E, empenhadas | 2014–2023 | 6 funções |
| População | `Dados Brutos/Base_Populacao_Municipal.xlsx` | SIDRA 6579 | 2014–2021 e 2024 | faltam 2022 e 2023 |
| PIB municipal | `Dados Brutos/Base_PIB_corrigida.xlsx` | IBGE, PIB dos Municípios (série revisada) | 2014–2023 | preços correntes |
| IDEB | `Dados Brutos/Base_IDEB_Camacari_Barreiras.xlsx` | QEdu/INEP | 2015–2023 (bienal) | valores "lidos do gráfico" |
| Hungria | `FSP P1/Dados tratados (Q1 a 10)/Hungria_2014_2023.xlsx` | Eurostat, KSH, OCDE, Banco Mundial, FMI | 2014–2023 | governo geral apenas |
| Deflator | (nas planilhas tratadas) | IPCA, SIDRA 1737 | — | preços de 2023 |

A P1 responde a 10 questões (composição da receita, Laffer, regressão receita–PIB, mapa per capita etc.). **Não estima o efeito flypaper** e não separa transferências condicionadas de incondicionadas.

## 2. Inconsistências encontradas

A coluna "Verificação" indica como cada item foi confirmado.

| # | Item | Achado | Verificação | Tratamento na P2 |
|---|---|---|---|---|
| A1 | Despesa por função: **zeros no lugar de ausentes** | 9 células com 0: Camaçari/Saúde 2019; Barreiras/Administração 2018; Barreiras/Saneamento 2014, 2017, 2018, 2020–2023. A função não aparece na aba bruta desses anos. | Automática (`achados_auditoria.csv`) | Gravar NaN. Saúde e Administração são lacunas de coleta (não existe gasto zero nessas funções) e serão preenchidas pela nova coleta. Saneamento pode ser gasto nulo de fato, porque a DCA omite funções sem empenho; registrar isso como hipótese. |
| A2 | **FPM com definição inconsistente** | Em 2016 (Barreiras) e 2017 (Camaçari), a P1 usou só a cota mensal e deixou de fora as parcelas de 1%. De 2018 em diante, somou as parcelas. Diferenças: +0,44% e **+9,0%**. | Automática, com o extrator novo | O FPM passa a ser a soma de todas as parcelas, com a mesma definição em todos os anos. |
| A3 | **Transferência extraordinária em Barreiras 2017** | R$ 178,6 mi em "1.7.2.4.99 – Outras Transferências Multigovernamentais", o que fez a receita total subir 49,8% em relação a 2016. A rubrica não aparece em outros anos. | Automática | Variável `rec_outras_multigov` em separado. Teste de sensibilidade com e sem esse valor (`rec_corrente_sem_extraord`). A natureza do repasse (p. ex. precatório do FUNDEF) **ainda não foi confirmada**: verificar no portal de transparência ou no TCM-BA antes de afirmar. |
| A4 | População 2022–2023 ausente | Os per capita desses anos ficaram vazios, e a série tem 2024, que fica fora do período. | Automática | Censo 2022 (SIDRA 4714) + estimativas de 2024–2025 (SIDRA 6579) + interpolação de 2023, com o preenchimento sinalizado. |
| A5 | Ano-base do deflator | A P1 usa IPCA a preços de 2023. | Leitura | Preços de 2025, pela média anual do IPCA. |
| A6 | Quebra de classificação de 2018 | A P1 não registra a mudança do ementário de receitas (2018) nem a de 2022. O mapeamento usa referências fixas de célula (`=C7`, `=C10`…), que dependem da posição da linha. | Leitura das abas | Extrator por código e rótulo (`rubricas_receita.py`) + `dummy_pos2018`. Validado: 118 de 120 valores coincidem com a P1; os 2 restantes são o caso A2. |
| A7 | Receita bruta × dedução do FUNDEB | A P1 calcula o resultado como "receita − despesa empenhada" com a receita da coluna "Valor". Se a coluna for a receita bruta, o superávit está superestimado no valor da dedução do FUNDEB. | **A confirmar** quando a nova coleta trouxer as duas colunas | `resultado_orcamentario` = receita líquida do FUNDEB − despesa. A definição antiga é mantida em `resultado_bruto_sem_deducao` para comparação. |
| A8 | IDEB | Os valores foram "lidos do gráfico" (print do QEdu), com precisão limitada. | Leitura da planilha | Se o IDEB for usado, baixar a planilha oficial do INEP por município. |
| A9 | Hungria: valores em HUF 2014–2021 são **estimativas** | Obtidos como % do PIB × PIB estimado (PIB em USD × câmbio médio). A própria planilha os marca como "ESTIMATIVAS". | Leitura da planilha | Usar Eurostat `gov_10a_main` em milhões de HUF (valor oficial), com uma fonte por série. |
| A10 | Hungria: fontes misturadas por linha | Receita/PIB vem de "Eurostat / IMF WEO" e despesa de "Eurostat / OECD". | Leitura | Uma fonte por série, com código do conjunto de dados e data de acesso. |
| A11 | Hungria: sem governo local | Só traz o governo geral (S13), sem o setor S1313 nem transferências entre níveis de governo. | Leitura | Ampliação: receita, despesa e transferências recebidas pelos governos locais (S1313), comparáveis às dos municípios. |
| A12 | Regressão Q7 da P1 | Receita real em nível contra PIB real em nível, juntando os dois municípios (N = 20, R² = 0,91). O R² alto vem da diferença de escala entre os municípios, não da relação ao longo do tempo. | Leitura | Modelo em logaritmos per capita, com efeito fixo de município e transferências incondicionais. Tratado como exploratório. |

## 3. O que se aproveita sem mudança

- As abas brutas de receitas de 2014–2023 são cópias fiéis do Finbra (o extrator reproduz a P1 em 118 de 120 valores) e servem de verificação cruzada para a nova coleta.
- O PIB municipal (série revisada do IBGE) é usado com a mesma definição.
- A seleção de despesas (Anexo I-D, empenhadas) segue o mesmo critério da P2.

## 4. Próximo passo

Quando a nova coleta estiver em `data/raw/`, o script `compara_original_atualizado.py` (a escrever) vai comparar ano a ano `painel_original.csv` com `tratado_municipios.csv` nos anos em comum (2014–2023). O resultado preenche a tabela "valor P1 × valor P2 × motivo" do registro de alterações.
