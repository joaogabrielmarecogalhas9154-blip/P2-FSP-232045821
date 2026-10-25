"""Figura da produção anual (bibliometria) a partir da exportação da Scopus.

Reproduz em Python a contagem do bibliometria.R: artigos de periódico de 2016 a 2026 e o subconjunto que trata de
efeito flypaper ou ilusão fiscal (termos no título, no resumo ou nas palavras-chave). Desenha barras empilhadas por
ano, com eixo de anos inteiros e 2026 marcado como parcial.
Uso (na raiz do repositório): python codigo/figura_bibliometria.py
"""
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ARQ = os.path.join("data", "bibliometria", "scopus_principal_2016_2026.bib")
FIG = os.path.join("artigo", "figuras")
RES = "resultados"
txt = open(ARQ, encoding="utf-8", errors="ignore").read()


def campo(ent, nome):
    m = re.search(nome + r"\s*=\s*\{(.*?)\},?\s*\n\s*[a-z_]+\s*=", ent + "\nfim = ", re.S | re.I)
    return m.group(1) if m else ""


regs = []
for ent in re.split(r"\n@", "\n" + txt)[1:]:
    tipo = ent.split("{", 1)[0].strip().upper()
    ano = campo(ent, "year")
    doc = campo(ent, "type").upper()
    if tipo != "ARTICLE" or not ano.isdigit():
        continue
    if doc and ("REVIEW" in doc or "CONFERENCE" in doc):
        continue
    corpo = " ".join(campo(ent, c) for c in ("title", "abstract", "author_keywords", "keywords")).upper()
    regs.append({"ano": int(ano), "especifico": bool(re.search(r"FLYPAPER|FLY PAPER|FLY-PAPER|FISCAL ILLUSION", corpo))})
d = pd.DataFrame(regs)
d = d[(d.ano >= 2016) & (d.ano <= 2026)]
cont = d.groupby(["ano", "especifico"]).size().unstack(fill_value=0).reindex(range(2016, 2027), fill_value=0)
cont.columns = ["outros" if not c else "flypaper_ilusao" for c in cont.columns]
cont.to_csv(os.path.join(RES, "bibliometria_producao_anual.csv"), encoding="utf-8-sig")
print(cont, "\nTotal:", int(cont.values.sum()), "| flypaper/ilusão:", int(cont["flypaper_ilusao"].sum()))

plt.rcParams.update({"font.family": "serif", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
fig, ax = plt.subplots(figsize=(7.2, 3.0))
x = cont.index.values
esp, out = cont["flypaper_ilusao"].values, cont["outros"].values
parc = x == 2026
ax.bar(x[~parc], esp[~parc], color="#eb6834", width=0.72, label="Flypaper ou ilusão fiscal")
ax.bar(x[~parc], out[~parc], bottom=esp[~parc], color="#2a78d6", width=0.72, label="Demais artigos sobre transferências")
ax.bar(x[parc], esp[parc], color="#eb6834", width=0.72, alpha=0.45, hatch="//", edgecolor="white")
ax.bar(x[parc], out[parc], bottom=esp[parc], color="#2a78d6", width=0.72, alpha=0.45, hatch="//", edgecolor="white")
for xi, tot in zip(x, esp + out):
    ax.text(xi, tot + 0.6, str(int(tot)), ha="center", va="bottom", fontsize=7.5, color="#1f1f1e")
ax.text(2026, (esp + out)[-1] + 4.5, "parcial", ha="center", fontsize=7, color="#5f5e58")
ax.set_xticks(x)
ax.set_xticklabels([str(a) for a in x])
ax.set_ylabel("Artigos por ano")
ax.set_ylim(0, max(esp + out) * 1.22)
ax.grid(axis="y", color="#e4e3de", lw=0.6)
ax.set_axisbelow(True)
ax.legend(frameon=False, loc="upper left", fontsize=8)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "figura_producao_anual.png"), dpi=220)
fig.savefig(os.path.join(FIG, "figura_producao_anual.pdf"))
