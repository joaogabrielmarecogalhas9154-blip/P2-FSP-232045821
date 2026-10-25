# Registro de alterações: P1 → P2

**Trabalho anterior:** João Paulo Cortes da Cunha Dutra (241021838), P1 de Finanças do Setor Público, 2026/1.
Repositório: https://github.com/Jhons777/P1-Finan-as-do-Setor-Publico---Jo-o-Paulo-Cortes-Da-Cunha-Dutra-241021838 (commit `4ae3ff4`, 08/05/2026).
**Nova versão (P2):** matrícula 232045821. Coleta feita em 21/10/2026 (ver `data/raw/log_coleta.csv` e `data/raw/log_coleta_hungria.csv`).

Os arquivos que sustentam cada linha deste registro são reproduzíveis:

| Arquivo | Conteúdo | Gerado por |
|---|---|---|
| `data/original/P1_anterior/` | cópia integral da P1, sem alteração | `git clone` (ver README) |
| `data/original/painel_original.csv` | base da P1 em formato tabular | `codigo/importa_base_original.py` |
| `data/original/achados_auditoria.csv` | inconsistências detectadas na P1 | `codigo/importa_base_original.py` |
| `data/registro_alteracoes/comparacao_P1_P2.csv` | 340 comparações valor a valor (município × ano × variável) com motivo | `codigo/compara_original_atualizado.py` |
| `data/registro_alteracoes/hungria_P1_P2.csv` | governo geral da Hungria: P1 × Eurostat | `codigo/tratamento_hungria.py` |

## 1. Resultado da comparação (municípios, 2014–2023, valores nominais)

Dos **340** valores comparáveis (17 variáveis × 2 municípios × 10 anos): **327 iguais** (diferença < 0,1%), **9 corrigidos** e **4 preenchidos**. Nenhuma diferença ficou sem explicação.

## 2. Correções

| # | Variável | Unidade e anos | Problema na P1 | Correção na P2 | Impacto |
|---|---|---|---|---|---|
| C1 | Receita total | Camaçari, 2019–2023 | Usou "Receitas (exceto intra-orçamentárias)", mas a despesa total inclui as intra-orçamentárias | Receita e despesa totais com intra-orçamentárias (mesma base) | Receita +1,8% a +5,5%; o resultado da P1 estava subestimado em R$ 31–111 mi/ano |
| C2 | Resultado orçamentário | ambos, 2014–2023 | Receita bruta − despesa, sem descontar a dedução para o FUNDEB | `resultado_orcamentario` = (receita total − dedução FUNDEB) − despesa empenhada | Dedução de R$ 28–158 mi/ano; superávit vira déficit em 7 município-anos (Barreiras 2014, 2015, 2020, 2022, 2023; Camaçari 2014, 2015). A definição antiga está em `resultado_bruto_sem_deducao` |
| C3 | FPM | Barreiras 2016; Camaçari 2017 | Contou só a cota mensal, sem as parcelas de 1%. De 2018 em diante as parcelas entram | Soma de todas as parcelas em todos os anos | +0,4% e +9,0% |
| C4 | Despesa em saúde | Camaçari 2019 | Gravou 0 (a função não estava na aba coletada) | Valor da DCA, Anexo I-E: R$ 239,3 mi | De zero para o valor real |
| C5 | Despesa por função (saneamento, administração) | Barreiras, vários anos | Zero no lugar de ausente | Tratados como ausentes (NaN) quando a função não consta na DCA; a P2 usa só Educação e Saúde | Não afeta os resultados da P2 |
| C6 | População | Barreiras 2018 | 158.331 (dígitos trocados) | 153.831 (IBGE, SIDRA 6579) | −2,8% |
| C7 | População | ambos, 2022–2023 | Ausente; per capita vazio | 2022 = Censo; 2023 = interpolação linear Censo 2022–estimativa 2024 (sinalizada em `pop_fonte`) | Per capita disponível em todos os anos |
| C8 | Hungria: receita e despesa do governo geral em HUF | 2014–2021 | Estimadas como % do PIB × PIB estimado (PIB em USD × câmbio) | Valor oficial do Eurostat (`gov_10a_main`, MIO_NAC) | Diferenças de −7,5% a +7,5% |
| C9 | Hungria: fontes por linha | 2014–2023 | Mistura de Eurostat, FMI e OCDE na mesma série | Uma fonte por série (Eurostat), com código do conjunto de dados e data de acesso | Consistência |
| C10 | Regressão da P1 (Q7) | — | Receita × PIB em nível, juntando dois municípios de escalas diferentes (R² = 0,91 por efeito de escala) | Modelo em log per capita com efeito fixo de município, transferências incondicionais e PIB | Nova análise |

**Observação (não é erro):** em 2017, Barreiras recebeu R$ 178,6 mi em "Outras Transferências Multigovernamentais" (conta 1.7.2.4.99), e a receita total subiu 49,8% no ano. A P2 mantém o valor (é dado oficial), mas o isola em `rec_outras_multigov` e o exclui de `rec_corrente_sem_extraord` e da figura de dependência. A origem do repasse ainda não foi confirmada em fonte primária.

## 3. Atualizações e ampliações

- **Período:** coleta de 2014 a 2025; análise de **2016 a 2025** (os 10 anos mais recentes com DCA completa). O PIB municipal vai só até **2023**, então regressões e razões sobre o PIB terminam em 2023.
- **Novas variáveis municipais:** transferências da União e do Estado; ITR; cotas de IPVA e IPI-exportação; SUS; transferências incondicionais; deduções do FUNDEB; despesa de pessoal; VAB setorial (até 2021); resultado orçamentário corrigido; todos os valores também em reais de 2025 (`_real`) e per capita (`_real_pc`).
- **Hungria:** governos locais (setor S1313) com receita, despesa, transferências recebidas (D73, D9), impostos, despesa por função (COFOG) e despesa local como proporção do governo geral, de 2012 a 2025. Deflator: HICP.
- **Deflator:** IPCA médio anual, preços de **2025** (a P1 usava 2023).
- **Quebras de série identificadas:** mudança no ementário da receita em **2018** e em **2022**. O código identifica cada conta por código + rótulo (`codigo/rubricas_receita.py`) e o modelo inclui `D2018`. A partir de 2018, o IPTU inclui multas e dívida ativa do imposto.

## 4. Materiais reaproveitados da P1

As abas brutas de receitas de 2014–2023 serviram para validar o extrator de rubricas (118 de 120 valores iguais; os 2 restantes são a correção C3). A seleção de despesas (Anexo I-D, empenhadas) e a série do PIB municipal (série revisada do IBGE) seguem os mesmos critérios da P1. Nenhum dado da P1 entra na base tratada: todos os valores da P2 foram coletados de novo nas fontes oficiais.
