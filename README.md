[README.md](https://github.com/user-attachments/files/33932092/README.md)
# P2 – Finanças do Setor Público (UnB, CCA0169, 2026.2)

**Dependência de transferências, autonomia fiscal e efeito *flypaper*: Barreiras e Camaçari (BA) e os governos locais da Hungria (2016–2025)**

João Gabriel Maréco Galhas · Matrícula **232045821** · Prof. Lucas Oliveira Gomes Ferreira

- Artigo: [`232045821_P2_FSP.pdf`](232045821_P2_FSP.pdf) (código-fonte LaTeX em `artigo/`); versão editável em Word: [`232045821_P2_FSP.docx`](232045821_P2_FSP.docx)
- Trabalho anterior (P1): João Paulo Cortes da Cunha Dutra (241021838), <https://github.com/Jhons777/P1-Finan-as-do-Setor-Publico---Jo-o-Paulo-Cortes-Da-Cunha-Dutra-241021838>

## Organização do repositório

```
├── 232045821_P2_FSP.pdf          artigo final
├── 232045821_P2_FSP.docx         mesmo artigo em Word (gerado do LaTeX por codigo/gera_docx.py)
├── P2_coleta_colab.ipynb         notebook que reproduz tudo no Google Colab
├── artigo/                       projeto LaTeX (Overleaf): main.tex, secoes/, tabelas/, figuras/, referencias.bib
├── codigo/                       scripts (ordem de execução abaixo)
├── data/
│   ├── original/                 DADOS ORIGINAIS: cópia integral da P1 (P1_anterior/) + versão tabular e auditoria
│   ├── raw/                      DADOS BRUTOS ATUALIZADOS: exatamente como baixados das fontes, + logs de coleta
│   ├── tratados/                 DADOS TRATADOS: painéis usados nas análises + arquivos de qualidade
│   └── registro_alteracoes/      comparação valor a valor P1 × P2, com o motivo de cada diferença
├── docs/
│   ├── registro_alteracoes.md    REGISTRO DAS ALTERAÇÕES (correções, atualizações, ampliações)
│   ├── auditoria_trabalho_anterior.md
│   └── dicionario_variaveis.md   DICIONÁRIO DE VARIÁVEIS (também em .csv)
├── referencias/                  listas de referências e triagem bibliográfica
└── resultados/                   saídas numéricas das análises (CSV)
```

## Como reproduzir

**Opção 1 – Google Colab (recomendado):** abra `P2_coleta_colab.ipynb` no Colab e use *Ambiente de execução → Executar tudo*. O notebook grava os scripts, baixa os dados, trata, analisa e gera um ZIP com tudo (~10 min).

**Opção 2 – local (Python 3.10+):** `pip install requests pandas numpy scipy matplotlib openpyxl` e, na raiz do repositório:

| Passo | Comando | O que faz |
|---|---|---|
| 1 | `python codigo/coleta_municipios.py` | Siconfi (DCA 2014–2025), IBGE (PIB, população, Censo 2022, IPCA) → `data/raw/` |
| 2 | `python codigo/coleta_hungria.py` | Banco Mundial (Hungria e Brasil) e Eurostat (governo geral e governos locais) → `data/raw/` |
| 3 | `python codigo/tratamento.py` | Painel dos municípios: rubricas, valores reais de 2025, per capita, razões → `data/tratados/` |
| 4 | `python codigo/tratamento_hungria.py` | Painel da Hungria (S1313), deflator HICP → `data/tratados/` |
| 5 | `git clone --depth 1 <link da P1> data/original/P1_anterior` e `python codigo/importa_base_original.py data/original/P1_anterior` | Base da P1 em CSV e auditoria |
| 6 | `python codigo/compara_original_atualizado.py` | Registro de alterações valor a valor |
| 7 | `python codigo/analise.py` | Descritivas, regressões em níveis (efeitos marginais), robustez e placebos, FPM, resultado orçamentário, Hungria; tabelas LaTeX e gráficos → `artigo/tabelas/`, `artigo/figuras/`, `resultados/` |
| 8 | `python codigo/gera_dicionario.py` | Dicionário de variáveis |
| 9 | `codigo/bibliometria.R` (RStudio) | Estudo bibliométrico com bibliometrix → `artigo/tabelas/tabela1_bibliometria.tex` |
| 9b | `python codigo/figura_bibliometria.py` | Figura da produção anual (total e flypaper/ilusão fiscal) a partir da exportação da Scopus |
| 10 | em `artigo/`: `pdflatex main && bibtex main && pdflatex main && pdflatex main` (ou Overleaf) | Compila o artigo em PDF |
| 11 | em `artigo/`: `python ../codigo/gera_docx.py` (requer pandoc e python-docx) | Gera a versão Word (capa, sumário, mesmas citações e referências do PDF); o LibreOffice, se instalado, preenche as páginas do sumário |

Parâmetros (municípios, país, anos, ano-base) ficam só em `codigo/config.py`.

## Fontes

| Dado | Fonte | Endereço |
|---|---|---|
| Receitas e despesas municipais (DCA, Anexos I-C, I-D, I-E) | Tesouro Nacional – Siconfi | <https://apidatalake.tesouro.gov.br/ords/siconfi/tt/dca> |
| PIB municipal e VAB (tab. 5938), população (6579), Censo 2022 (4714), IPCA (1737) | IBGE – SIDRA | <https://sidra.ibge.gov.br> |
| Finanças do governo geral e dos governos locais da Hungria | Eurostat (`gov_10a_main`, `gov_10a_exp`, `gov_10a_taxag`) | <https://ec.europa.eu/eurostat/databrowser> |
| Inflação da Hungria (HICP) | Eurostat (`prc_hicp_aind`) | idem |
| PIB, população, câmbio (Hungria e Brasil) | Banco Mundial – WDI | <https://data.worldbank.org> |

## Regras de tratamento

- Valores monetários em termos reais: **IPCA médio anual, preços de 2025** (Brasil) e **HICP médio anual, preços de 2025** (Hungria).
- **Dados ausentes nunca são substituídos por zero**: permanecem vazios e aparecem em `data/tratados/qualidade_celulas_vazias.csv`.
- Quebras de série: ementário da receita em 2018 e 2022 (identificação por código + rótulo; dummy `D2018`); população de 2022 pelo Censo.
- A comparação município × país usa razões e % do PIB, nunca valores absolutos em moedas diferentes.

## Cobertura e justificativas

| Variável / unidade | Período | Por quê |
|---|---|---|
| Receitas e despesas (Barreiras e Camaçari) | 2016–2025 na análise; coleta 2014–2025 | Dez anos mais recentes com DCA completa; 2014–2015 coletados só para comparar com a P1 (2014–2023) |
| PIB municipal e VAB | 2014–2023 | O IBGE ainda não publicou 2024 e 2025; por isso as regressões param em 2023 |
| População | 2014–2025 | 2022 = Censo; 2023 interpolada entre o Censo e a estimativa de 2024 (sinalizada na base) |
| Governos locais da Hungria (Eurostat S1313) | 2012–2025 | Série completa disponível; começa um ano após o início da recentralização (2011) |
| FPM (coeficientes) | 2016–2025 | Iguais desde 2018; LC 165/2019 congelou os coeficientes até o Censo 2022 |

## Materiais reaproveitados da P1

A cópia integral da P1 está em `data/original/P1_anterior/`. As abas brutas de receitas serviram para validar o extrator de rubricas. Nenhum valor da P1 entra na base tratada: todos foram coletados de novo nas fontes. Detalhes em `docs/registro_alteracoes.md`.
