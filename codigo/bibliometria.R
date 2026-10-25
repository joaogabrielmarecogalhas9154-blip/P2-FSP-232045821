# =====================================================================================
# P2 - Finanças do Setor Público (UnB) - Estudo bibliométrico (bibliometrix)
# Gera a "Tabela 1" (CSV e LaTeX, em tabelas/tabela1_bibliometria.tex) no formato de Baker, Larcker e Wang (2022, JFE): todos os artigos x subconjunto específico, por periódico
# e por período, com a nota da busca preenchida automaticamente; gráfico de produção anual;
# resumo do biblioAnalysis; lista dos artigos mais citados para a triagem das 80 referências.
#
# ANTES DE RODAR
# 1) Busca (via Periódicos CAPES / CAFe UnB). Anote a DATA da busca.
#    Scopus (Advanced search):
#      TITLE-ABS-KEY ( "flypaper effect" OR "fiscal illusion" OR "intergovernmental transfer*"
#        OR "intergovernmental grant*" ) AND TITLE-ABS-KEY ( municipal* OR "local government*"
#        OR subnational ) AND PUBYEAR > 2015 AND ( LIMIT-TO ( DOCTYPE , "ar" ) )
#      Exportar: marque "Select all" (TODOS os resultados, não só a página) -> Export -> BibTeX,
#      marcando TODAS as informações (citação, resumo, palavras-chave, referências).
#      Se passar de 2.000 registros, exporte em partes (por faixa de anos) e liste todos em ARQ_SCOPUS.
#    Web of Science (opcional, Core Collection):
#      TS=(("flypaper effect" OR "fiscal illusion" OR "intergovernmental transfer*" OR
#          "intergovernmental grant*") AND (municipal* OR "local government*" OR subnational))
#      Filtros: Document Types = Article; anos 2016-2026. Exportar: Plain text, "Full Record and
#      Cited References" (500 por vez).
# 2) No RStudio: File > Open File... > este script > botão "Source" (canto superior direito do editor).
#    Uma janela pede o arquivo .bib da Scopus. As saídas são gravadas na MESMA pasta do .bib:
#    resultados_bibliometria/, tabelas/tabela1_bibliometria.tex e figuras/figura_producao_anual.png.
#    Depois, para explorar e gerar figuras extras (mapa temático, coocorrência):
#      library(bibliometrix); biblioshiny()   -> carregar o mesmo arquivo exportado.
# =====================================================================================

pacotes <- c("bibliometrix", "dplyr", "tidyr", "ggplot2")
faltam <- pacotes[!pacotes %in% rownames(installed.packages())]
if (length(faltam)) install.packages(faltam)
library(bibliometrix); library(dplyr); library(tidyr); library(ggplot2)

# ------------------------------------------------------------------ parâmetros
DATA_BUSCA  <- "AAAA-MM-DD"                           # <- preencher com a data real da busca (ex.: "2026-10-22")
ANO_MIN <- 2016; ANO_MAX <- 2026                       # últimos 10 anos
ARQ_SCOPUS  <- c("data/bibliometria/scopus.bib")      # um ou mais arquivos; se não existir, abre uma janela
ARQ_WOS     <- c("data/bibliometria/savedrecs.txt")   # opcional (Web of Science)
if (!any(file.exists(ARQ_SCOPUS))) {
  message("Escolha o arquivo .bib exportado da Scopus na janela que vai abrir...")
  ARQ_SCOPUS <- file.choose()
  setwd(dirname(ARQ_SCOPUS))                           # saídas ficam na pasta do .bib
}
OUT <- "resultados_bibliometria"
dir.create(OUT, recursive = TRUE, showWarnings = FALSE)

# ------------------------------------------------------------------ leitura
ler <- function(arqs, db, fmt) {
  arqs <- arqs[file.exists(arqs)]
  if (!length(arqs)) return(NULL)
  convert2df(arqs, dbsource = db, format = fmt)
}
S <- ler(ARQ_SCOPUS, "scopus", "bibtex")
W <- ler(ARQ_WOS, "wos", "plaintext")
if (is.null(S) && is.null(W)) stop("Nenhum arquivo exportado encontrado em data/bibliometria/")
M <- if (!is.null(S) && !is.null(W)) mergeDbSources(S, W, remove.duplicated = TRUE) else if (!is.null(S)) S else W
bases_usadas <- paste(c(if (!is.null(S)) "Scopus", if (!is.null(W)) "Web of Science"), collapse = " e ")
n_bruto <- nrow(M)

# Filtro: só artigos de periódico, 2000-2026 (subset em R base preserva os atributos do bibliometrix)
M$PY <- suppressWarnings(as.integer(M$PY))
manter <- grepl("ARTICLE", toupper(M$DT)) & !grepl("REVIEW|CONFERENCE|PROCEEDINGS", toupper(M$DT)) &
          !is.na(M$PY) & M$PY >= ANO_MIN & M$PY <= ANO_MAX
M <- M[manter, ]
n_final <- nrow(M)
saveRDS(M, file.path(OUT, "base_bibliometrica.rds"))

# ------------------------------------------------------------------ Tabela 1 (formato Baker et al., 2022)
# Mesma lógica da Tabela 1 de Baker et al.: (1) todos os artigos da busca; (2) o subconjunto específico
# (artigos que tratam de efeito flypaper ou ilusão fiscal, no título, resumo ou palavras-chave);
# (3) participação de (2) em (1), por periódico.
campos_txt <- toupper(paste(M$TI, M$AB, M$DE, M$ID))
M$especifico <- grepl("FLYPAPER|FLY PAPER|FLY-PAPER|FISCAL ILLUSION", campos_txt)
top10 <- names(sort(table(M$SO), decreasing = TRUE))[1:min(10, length(unique(M$SO)))]
tab <- M %>%
  mutate(Periodico = ifelse(SO %in% top10, tools::toTitleCase(tolower(SO)), "Demais periódicos")) %>%
  group_by(Periodico) %>%
  summarise(Todos = n(), Especificos = sum(especifico), .groups = "drop") %>%
  arrange(Periodico == "Demais periódicos", desc(Todos), Periodico)
tab <- bind_rows(tab, tibble(Periodico = "Total", Todos = sum(tab$Todos), Especificos = sum(tab$Especificos)))
tab$Proporcao <- gsub(".", ",", sprintf("%.1f%%", 100 * tab$Especificos / tab$Todos), fixed = TRUE)
write.csv(tab, file.path(OUT, "tabela1_artigos_por_periodico.csv"), row.names = FALSE, fileEncoding = "UTF-8")
# distribuição por período (vai para o texto e a figura)
M$periodo <- cut(M$PY, breaks = c(ANO_MIN - 1, 2019, 2022, ANO_MAX),
                 labels = c(paste0(ANO_MIN, "-2019"), "2020-2022", paste0("2023-", ANO_MAX)))
write.csv(as.data.frame(table(M$periodo, M$especifico, dnn = c("periodo", "especifico"))),
          file.path(OUT, "artigos_por_periodo.csv"), row.names = FALSE, fileEncoding = "UTF-8")

data_br <- tryCatch(format(as.Date(DATA_BUSCA), "%d/%m/%Y"), error = function(e) DATA_BUSCA)
ano_parcial <- suppressWarnings(as.integer(substr(DATA_BUSCA, 1, 4)))
frase_parcial <- if (!is.na(ano_parcial) && ano_parcial == ANO_MAX)
  sprintf(" Os dados de %d são parciais (artigos indexados até a data da busca).", ANO_MAX) else ""
nota <- sprintf(paste0(
  "Nota: A tabela resume o número de artigos publicados em periódicos científicos entre %d e %d sobre ",
  "transferências intergovernamentais a governos locais. A busca foi realizada em %s na base %s, nos campos título, ",
  "resumo e palavras-chave, com a expressão: (\"flypaper effect\" OR \"fiscal illusion\" OR \"intergovernmental transfer*\" ",
  "OR \"intergovernmental grant*\") AND (municipal* OR \"local government*\" OR subnational), restrita a artigos de ",
  "periódico publicados entre %d e %d%s. A busca retornou %d artigos. A coluna (1) apresenta todos os artigos; a coluna (2), ",
  "os que tratam especificamente de efeito flypaper ou de ilusão fiscal (termos presentes no título, no resumo ou nas ",
  "palavras-chave); a coluna (3), a participação de (2) em (1). As linhas listam os dez periódicos com mais artigos; os ",
  "demais estão agregados.%s Processamento: pacote bibliometrix (Aria e Cuccurullo, 2017) no R."),
  ANO_MIN, ANO_MAX, data_br, bases_usadas, ANO_MIN, ANO_MAX,
  if (!is.null(S) && !is.null(W)) ", após remover duplicatas entre as bases" else "", n_final, frase_parcial)
writeLines(nota, file.path(OUT, "tabela1_nota.txt"), useBytes = TRUE)

# ------------------------------------------------------------------ Tabela 1 em LaTeX (para o Overleaf)
esc <- function(x) gsub("([&%$#_{}])", "\\\\\\1", as.character(x))
linhas_tex <- apply(tab, 1, function(r) paste(esc(trimws(r)), collapse = " & "))
n_total <- nrow(tab)
corpo <- c(paste0(linhas_tex[-n_total], " \\\\"), "\\midrule", paste0(linhas_tex[n_total], " \\\\"))
tex <- c(
  "\\begin{table}[H]", "\\centering\\footnotesize\\setlength{\\tabcolsep}{5pt}",
  "\\caption{Uso dos conceitos de efeito \\textit{flypaper} e ilusão fiscal na literatura sobre transferências a governos locais, por periódico (2016--2026)}",
  "\\label{tab:bibliometria}", "\\begin{threeparttable}",
  "\\begin{tabular}{lccc}", "\\toprule",
  " & (1) & (2) & (3) \\\\",
  " & Transferências a & \\textit{Flypaper} ou & (2)/(1) \\\\",
  "Periódico & governos locais & ilusão fiscal & (\\%) \\\\", "\\midrule",
  corpo, "\\bottomrule", "\\end{tabular}",
  "\\begin{tablenotes}[flushleft]\\footnotesize", paste0("\\item ", esc(nota)), "\\end{tablenotes}",
  "\\end{threeparttable}", "\\end{table}")
dir.create("tabelas", showWarnings = FALSE)
writeLines(tex, "tabelas/tabela1_bibliometria.tex", useBytes = TRUE)

# ------------------------------------------------------------------ Figura: produção anual
anual <- M %>% count(PY)
anual$parcial <- !is.na(ano_parcial) & anual$PY == ano_parcial
g <- ggplot(anual, aes(PY, n, fill = parcial)) + geom_col(width = 0.75) +
  geom_text(aes(label = n), vjust = -0.4, size = 3.2, colour = "#1f1f1e") +
  scale_fill_manual(values = c(`FALSE` = "#2a78d6", `TRUE` = "#9ec5f4"), guide = "none") +
  scale_x_continuous(breaks = ANO_MIN:ANO_MAX,
                     labels = ifelse(ANO_MIN:ANO_MAX == ano_parcial & !is.na(ano_parcial),
                                     paste0(ANO_MIN:ANO_MAX, "*"), ANO_MIN:ANO_MAX)) +
  scale_y_continuous(expand = expansion(mult = c(0, 0.08))) +
  labs(x = "Ano de publicação", y = "Número de artigos",
       caption = sprintf("Fonte: %s, busca em %s. Elaboração própria com bibliometrix.%s", bases_usadas, data_br,
                         if (any(anual$parcial)) sprintf(" * %d: ano parcial.", ano_parcial) else "")) +
  theme_minimal(base_size = 11) + theme(panel.grid.major.x = element_blank(), panel.grid.minor = element_blank())
ggsave(file.path(OUT, "figura_producao_anual.png"), g, width = 8, height = 4, dpi = 300)
dir.create("figuras", showWarnings = FALSE)
file.copy(file.path(OUT, "figura_producao_anual.png"), "figuras/figura_producao_anual.png", overwrite = TRUE)

# ------------------------------------------------------------------ resumo do bibliometrix
res <- biblioAnalysis(M, sep = ";")
sink(file.path(OUT, "resumo_biblioAnalysis.txt")); summary(res, k = 15, pause = FALSE); sink()

# ------------------------------------------------------------------ lista para triagem das 80 referências
cit <- M %>%
  transmute(autores = AU, ano = PY, titulo = TI, periodico = SO, doi = toupper(DI),
            citacoes = suppressWarnings(as.numeric(TC))) %>%
  arrange(desc(citacoes))
mestra <- "referencias/lista_mestra_referencias.csv"
if (file.exists(mestra)) {
  lm <- read.csv(mestra, encoding = "UTF-8")
  dois <- toupper(regmatches(lm$referencia, regexpr("10\\.[0-9]{4,}/[^ ,;]+", lm$referencia)))
  cit$ja_na_lista_mestra <- !is.na(cit$doi) & cit$doi != "" & cit$doi %in% dois
}
write.csv(cit, file.path(OUT, "triagem_mais_citados.csv"), row.names = FALSE, fileEncoding = "UTF-8")

cat("\nRegistros brutos:", n_bruto, "| artigos após filtro:", n_final, "\n")
print(tab)
cat("\n", nota, "\n")
