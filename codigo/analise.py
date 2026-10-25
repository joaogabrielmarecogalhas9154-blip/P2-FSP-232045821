"""
P2 - Análise: estatísticas descritivas, composição da receita, regressões do efeito flypaper,
indicadores da Hungria, gráficos e tabelas em LaTeX (prontas para o Overleaf).

Entradas: data/tratados/tratado_municipios.csv, data/tratados/tratado_hungria.csv,
          data/registro_alteracoes/comparacao_P1_P2.csv, data/registro_alteracoes/hungria_P1_P2.csv
Saídas:   artigo/tabelas/*.tex, artigo/figuras/*.pdf, resultados/*.csv
Uso:      python codigo/analise.py      (só numpy, pandas, scipy e matplotlib)

Regressão (MQO com efeito fixo de município, erros-padrão robustos HC1):
    ln G_it = a_i + bT ln T_it + bY ln Y_it + d D2018_t + e_it
G = despesa real per capita; T = transferências incondicionais reais per capita; Y = PIB real per capita.
O PIB municipal só existe até 2023, por isso a amostra da regressão termina em 2023.
Com N pequeno, os resultados são exploratórios (associação, não causalidade).
"""
import os
import sys
import numpy as np
import pandas as pd
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import JANELA_ANALISE, ANO_BASE  # noqa: E402

TAB = os.path.join("artigo", "tabelas"); FIG = os.path.join("artigo", "figuras"); RES = "resultados"
for d in (TAB, FIG, RES):
    os.makedirs(d, exist_ok=True)
A0, A1 = JANELA_ANALISE
COR = {"Barreiras": "#2a78d6", "Camaçari": "#eb6834", "Hungria": "#1baf7a"}   # validado (dataviz)
TINTA, TINTA2, GRADE = "#1f1f1e", "#5f5e58", "#e4e3de"
plt.rcParams.update({"font.family": "serif", "font.size": 9, "axes.edgecolor": TINTA2, "axes.labelcolor": TINTA,
                     "xtick.color": TINTA2, "ytick.color": TINTA2, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": GRADE, "grid.linewidth": 0.6,
                     "axes.axisbelow": True, "legend.frameon": False})


# ------------------------------------------------------------------ utilidades
def br(x, d=0):
    """Número no padrão brasileiro (1.234,5). NaN vira '--' (ausente, nunca zero)."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "--"
    s = f"{x:,.{d}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def pct(x, d=1):
    return "--" if pd.isna(x) else br(100 * x, d) + "\\%"


def tabela_tex(nome, legenda, rotulo, cabecalho, linhas, nota, alinhamento=None, fonte_peq=True):
    """Tabela booktabs; reduz automaticamente para caber na largura do texto (adjustbox) e põe a nota embaixo."""
    al = alinhamento or ("l" + "r" * (len(cabecalho) - 1))
    tex = ["\\begin{table}[H]", "\\centering" + ("\\footnotesize" if fonte_peq else ""),
           "\\setlength{\\tabcolsep}{4pt}", f"\\caption{{{legenda}}}", f"\\label{{{rotulo}}}",
           "\\begin{adjustbox}{max width=\\textwidth}", f"\\begin{{tabular}}{{{al}}}", "\\toprule",
           " & ".join(cabecalho) + " \\\\", "\\midrule"]
    for ln in linhas:
        tex.append(ln if isinstance(ln, str) else " & ".join(ln) + " \\\\")
    tex += ["\\bottomrule", "\\end{tabular}", "\\end{adjustbox}",
            "\\par\\vspace{3pt}\\parbox{\\textwidth}{\\scriptsize " + nota + "}", "\\end{table}"]
    with open(os.path.join(TAB, nome), "w", encoding="utf-8") as f:
        f.write("\n".join(tex) + "\n")


def mqo_hc1(y, X, nomes):
    """MQO com erros robustos HC1. Retorna dict com coeficientes, ep, p, N, R2, DW e matriz de covariância."""
    y, X = np.asarray(y, float), np.asarray(X, float)
    n, k = X.shape
    XtX_inv = np.linalg.inv(X.T @ X)
    b = XtX_inv @ X.T @ y
    e = y - X @ b
    V = n / (n - k) * XtX_inv @ (X.T * e ** 2) @ X @ XtX_inv
    ep = np.sqrt(np.diag(V))
    p = 2 * stats.t.sf(np.abs(b / ep), n - k)
    r2 = 1 - (e @ e) / np.sum((y - y.mean()) ** 2)
    dw = np.sum(np.diff(e) ** 2) / (e @ e)
    return {"b": dict(zip(nomes, b)), "ep": dict(zip(nomes, ep)), "p": dict(zip(nomes, p)), "n": n, "k": k,
            "r2": r2, "dw": dw, "V": pd.DataFrame(V, index=nomes, columns=nomes), "resid": e}


def wald_igualdade(r, a, b):
    """H0: coef[a] = coef[b] (teste t com covariância HC1)."""
    d = r["b"][a] - r["b"][b]
    var = r["V"].loc[a, a] + r["V"].loc[b, b] - 2 * r["V"].loc[a, b]
    t = d / np.sqrt(var)
    return d, 2 * stats.t.sf(abs(t), r["n"] - r["k"])


def estrelas(p):
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.1 else ""


# ------------------------------------------------------------------ dados
t = pd.read_csv(os.path.join("data", "tratados", "tratado_municipios.csv")).copy()
h = pd.read_csv(os.path.join("data", "tratados", "tratado_hungria.csv")).set_index("ano")
t["impostos_proprios_real_pc"] = t[["rec_iptu_real_pc", "rec_iss_real_pc", "rec_itbi_real_pc"]].sum(axis=1, min_count=3)
t["outras_incond_real_pc"] = t[["rec_itr_real_pc", "rec_ipva_cota_real_pc", "rec_ipi_exp_cota_real_pc"]].sum(axis=1, min_count=1)
t["impostos_proprios_sobre_rc"] = t["impostos_proprios"] / t["rec_corrente"]
t["fpm_sobre_rc"] = t["rec_fpm"] / t["rec_corrente"]
t["icms_sobre_rc"] = t["rec_icms_cota"] / t["rec_corrente"]
t["transf_sem_icms_sobre_rc"] = (t["rec_transf_correntes"] - t["rec_icms_cota"]) / t["rec_corrente"]
t["transf_liq_sobre_rc_liq"] = (t["rec_transf_correntes"] - t["ded_fundeb_corrente"].abs()) / (t["rec_corrente"] - t["ded_fundeb_corrente"].abs())
t["transf_corr_sobre_rc_sem_extra"] = (t["rec_transf_correntes"] - t["rec_outras_multigov"].fillna(0)) / t["rec_corrente_sem_extraord"]
j = t[(t.ano >= A0) & (t.ano <= A1)].copy()
MUN = ["Barreiras", "Camaçari"]

# ------------------------------------------------------------------ Tabela: estatísticas descritivas
VARS = [("rec_corrente_real_pc", "Receita corrente"), ("impostos_proprios_real_pc", "Impostos próprios$^{b}$"),
        ("rec_transf_incondicionais_real_pc", "Transf. incondicionais$^{c}$"), ("rec_fpm_real_pc", "\\quad FPM"),
        ("rec_icms_cota_real_pc", "\\quad Cota-parte do ICMS"), ("rec_fundeb_real_pc", "FUNDEB"),
        ("desp_total_real_pc", "Despesa total"), ("desp_educacao_real_pc", "\\quad Educação"),
        ("desp_saude_real_pc", "\\quad Saúde"), ("pib_nominal_real_pc", "PIB per capita$^{a}$")]
linhas, desc = [], []
for v, rot in VARS:
    cel = [rot]
    for m in MUN:
        s = j.loc[j.municipio == m, v].dropna()
        cel += [br(s.mean()), br(s.std()), br(s.min()), br(s.max())]
        desc.append({"variavel": v, "municipio": m, "media": s.mean(), "dp": s.std(), "min": s.min(), "max": s.max(), "n": len(s)})
    linhas.append(cel)
pd.DataFrame(desc).to_csv(os.path.join(RES, "descritivas.csv"), index=False, encoding="utf-8-sig")
tabela_tex("tab_descritivas.tex",
           f"Estatísticas descritivas: valores reais per capita, Barreiras e Camaçari ({A0}--{A1})", "tab:descritivas",
           ["R\\$ de %d per capita" % ANO_BASE, "Média", "DP", "Mín.", "Máx.", "Média", "DP", "Mín.", "Máx."],
           linhas,
           (f"Nota: {A1 - A0 + 1} observações anuais por município, exceto (a) PIB, disponível até 2023 ({2023 - A0 + 1} anos). "
            f"Valores deflacionados pela média anual do IPCA (preços de {ANO_BASE}) e divididos pela população (estimativas do IBGE; "
            "Censo 2022 em 2022 e interpolação linear em 2023). (b) IPTU + ISS + ITBI. (c) FPM + ITR + cotas-partes de ICMS, "
            "IPVA e IPI-exportação + IOF-ouro. Despesa: empenhada. DP = desvio-padrão. Fonte: elaboração própria com dados do Siconfi (DCA) e do IBGE."),
           alinhamento="lrrrrrrrr")
# insere o cabeçalho de dois níveis (Barreiras / Camaçari)
f = os.path.join(TAB, "tab_descritivas.tex"); s = open(f, encoding="utf-8").read()
s = s.replace("\\toprule\n", "\\toprule\n & \\multicolumn{4}{c}{Barreiras} & \\multicolumn{4}{c}{Camaçari} \\\\\n"
              "\\cmidrule(lr){2-5}\\cmidrule(lr){6-9}\n", 1)
open(f, "w", encoding="utf-8").write(s)

# ------------------------------------------------------------------ Tabela: composição e dependência
ANOS_C = [a for a in [2016, 2019, 2022, 2025] if A0 <= a <= A1]
IND = [("fpm_sobre_rc", "FPM"), ("icms_sobre_rc", "Cota-parte do ICMS"),
       ("transf_incond_sobre_rec_corrente", "Transf. incondicionais"),
       ("transf_sobre_rec_corrente", "Transf. correntes (total)"),
       ("transf_liq_sobre_rc_liq", "Transf. correntes, líquidas da dedução$^{a}$"),
       ("transf_sem_icms_sobre_rc", "Transf. correntes sem a cota do ICMS$^{b}$"),
       ("impostos_proprios_sobre_rc", "Impostos próprios"),
       ("tributaria_sobre_rec_corrente", "Receita tributária")]
linhas, comp = [], []
for v, rot in IND:
    cel = [rot]
    for m in MUN:
        for a in ANOS_C:
            x = t.loc[(t.municipio == m) & (t.ano == a), v]
            x = float(x.iloc[0]) if len(x) else np.nan
            cel.append(pct(x)); comp.append({"indicador": v, "municipio": m, "ano": a, "valor": x})
    linhas.append(cel)
pd.DataFrame(comp).to_csv(os.path.join(RES, "composicao_receita.csv"), index=False, encoding="utf-8-sig")
tabela_tex("tab_composicao.tex", "Composição da receita corrente: participação de cada fonte (\\% da receita corrente)",
           "tab:composicao", ["Fonte"] + [str(a) for a in ANOS_C] * 2, linhas,
           ("Nota: razões calculadas com valores nominais do mesmo ano. A receita corrente é bruta (inclui as transferências do "
            "FUNDEB antes da dedução). (a) Transferências correntes menos a dedução para o FUNDEB, divididas pela receita corrente "
            "também líquida da dedução, para não contar duas vezes os 20\\% retidos do FPM e das cotas e devolvidos pelo fundo. (b) Transferências correntes menos a cota-parte do ICMS, divididas pela receita corrente. Anos selecionados do período 2016--2025. Em 2017, Barreiras registrou R\\$ 178,6 milhões em ``Outras Transferências "
            "Multigovernamentais'', que elevam a participação das transferências naquele ano (não exibido). Fonte: elaboração "
            "própria com dados do Siconfi (DCA, Anexo I-C)."), alinhamento="l" + "r" * (2 * len(ANOS_C)))
f = os.path.join(TAB, "tab_composicao.tex"); s = open(f, encoding="utf-8").read()
nA = len(ANOS_C)
s = s.replace("\\toprule\n", "\\toprule\n & \\multicolumn{%d}{c}{Barreiras} & \\multicolumn{%d}{c}{Camaçari} \\\\\n"
              "\\cmidrule(lr){2-%d}\\cmidrule(lr){%d-%d}\n" % (nA, nA, nA + 1, nA + 2, 2 * nA + 1), 1)
open(f, "w", encoding="utf-8").write(s)

# ------------------------------------------------------------------ Regressões (efeito flypaper)
# O teorema da equivalência compara EFEITOS MARGINAIS: dG/dT = dG/dY (reais de gasto por real de transferência e
# por real de renda). Igualdade de elasticidades em logaritmo não é a hipótese nula correta, porque Y per capita é
# dezenas de vezes maior que T per capita. O modelo principal é, por isso, estimado em níveis per capita:
#     G_it = a_i + gT T_it + gY Y_it + d D2018_t + e_it      H0 (equivalência): gT = gY
# T* = T sem a cota-parte do ICMS (FPM + ITR + cotas de IPVA e IPI-exportação). Robustez e placebos na Tabela 7.
# Com dois municípios e ~10 anos, tudo é exploratório: associação, não causalidade.
r_ = t.copy()
r_["fe_cam"] = (r_.municipio == "Camaçari").astype(float); r_["bar"] = 1 - r_["fe_cam"]
r_["G"] = r_.desp_total_real_pc; r_["Gc"] = r_.desp_corrente_real_pc
r_["T"] = r_.rec_transf_incondicionais_real_pc; r_["Y"] = r_.pib_nominal_real_pc
r_["Ts"] = r_[["rec_fpm_real_pc", "rec_itr_real_pc", "rec_ipva_cota_real_pc", "rec_ipi_exp_cota_real_pc"]].sum(axis=1, min_count=1)
r_["T_sem_icms"] = r_["Ts"]
r_["FPM"] = r_.rec_fpm_real_pc; r_["ICMS"] = r_.rec_icms_cota_real_pc
r_["FUNDEB"] = r_.rec_fundeb_real_pc; r_["SUS"] = r_.rec_sus_real_pc
r_["D"] = r_.dummy_pos2018; r_["tend"] = r_.ano - 2014
r_["Ts_bar"] = r_.Ts * r_.bar
amp = r_[(r_.ano >= 2014) & (r_.ano <= 2023)].dropna(subset=["G", "Gc", "T", "Y"]).sort_values(["municipio", "ano"])


def fe(d, dep, regs, extra=("D",)):
    d = d.dropna(subset=[dep] + list(regs)).sort_values(["municipio", "ano"])
    nomes = ["const", "fe_cam"] + list(regs) + list(extra)
    X = np.column_stack([np.ones(len(d)), d.fe_cam] + [d[c] for c in regs] + [d[c] for c in extra])
    return mqo_hc1(d[dep], X, nomes), d


def comb(r, pesos):
    """Combinação linear dos coeficientes (soma de peso x coef.), com EP HC1 e p bicaudal."""
    a = pd.Series(pesos).reindex(r["V"].index).fillna(0.0)
    b = pd.Series(r["b"]).reindex(r["V"].index)
    est = float(a @ b); ep = float(np.sqrt(a @ r["V"] @ a))
    return est, ep, 2 * stats.t.sf(abs(est / ep), r["n"] - r["k"])


# Tabela 6: modelo principal em níveis
princ = [("(1)", "$G$", ["T", "Y"]), ("(2)", "$G^{c}$", ["T", "Y"]), ("(3)", "$G$", ["Ts", "Y"]),
         ("(4)", "$G^{c}$", ["Ts", "Y"]), ("(5)", "$G^{c}$", ["FPM", "ICMS", "Y"])]
res6 = []
for nm, dep_rot, regs in princ:
    dep = "Gc" if "c" in dep_rot else "G"
    r, d = fe(amp, dep, regs)
    k = regs[0]
    dif, ep_d, p_d = comb(r, {k: 1, "Y": -1})
    p_fi = comb(r, {"FPM": 1, "ICMS": -1})[2] if "ICMS" in regs else np.nan
    res6.append(dict(modelo=nm, dep=dep_rot, regs=regs, r=r, k=k, dif=dif, ep_d=ep_d, p_d=p_d, p_fi=p_fi))
ROT = {"T": "$T$ (incondicionais)", "Ts": "$T^{*}$ (sem a cota do ICMS)", "FPM": "FPM", "ICMS": "Cota-parte do ICMS",
       "Y": "$Y$ (PIB)", "D": "$D2018$"}
linhas = []
for v in ["T", "Ts", "FPM", "ICMS", "Y", "D"]:
    a_, b_ = [ROT[v]], [""]
    for z in res6:
        r = z["r"]
        if v in r["b"]:
            a_.append(br(r["b"][v], 3) + estrelas(r["p"][v])); b_.append("(" + br(r["ep"][v], 3) + ")")
        else:
            a_.append(""); b_.append("")
    linhas += [a_, b_]
linhas.append("\\midrule")
linhas.append(["Efeito fixo de município"] + ["Sim"] * len(res6))
linhas.append(["$\\gamma_{\\text{transf.}} - \\gamma_Y$"] + [br(z["dif"], 2) + estrelas(z["p_d"]) for z in res6])
linhas.append([""] + ["(" + br(z["ep_d"], 2) + ")" for z in res6])
linhas.append(["IC 95\\% da diferença"] + ["[%s; %s]" % (br(z["dif"] - stats.t.ppf(.975, z["r"]["n"] - z["r"]["k"]) * z["ep_d"], 2),
                                                        br(z["dif"] + stats.t.ppf(.975, z["r"]["n"] - z["r"]["k"]) * z["ep_d"], 2)) for z in res6])
linhas.append(["$p$ ($H_0$: FPM = ICMS)"] + [("--" if np.isnan(z["p_fi"]) else br(z["p_fi"], 3)) for z in res6])
linhas.append(["Observações"] + [str(z["r"]["n"]) for z in res6])
linhas.append(["$R^2$"] + [br(z["r"]["r2"], 3) for z in res6])
linhas.append(["Durbin-Watson"] + [br(z["r"]["dw"], 2) for z in res6])
w_ = lambda d, c: d[c] - d.groupby("municipio")[c].transform("mean")  # noqa: E731
corr = {c: np.corrcoef(w_(amp, c), w_(amp, "Y"))[0, 1] for c in ["T", "Ts", "ICMS", "FPM"]}
icms_share = (amp.rec_icms_cota / amp.rec_transf_incondicionais).groupby(amp.municipio).mean()
tabela_tex("tab_regressao.tex",
           "Gasto municipal, transferências e PIB: efeitos marginais estimados em níveis per capita (2014--2023)",
           "tab:regressao", ["", *[z["modelo"] for z in res6]],
           [["Variável dependente"] + [z["dep"] for z in res6], "\\midrule"] + linhas,
           ("Nota: MQO com efeito fixo de município; variáveis em R\\$ de %d per capita; erros-padrão robustos HC1 entre "
            "parênteses; *** $p<0{,}01$, ** $p<0{,}05$, * $p<0{,}1$. Os coeficientes são efeitos marginais: reais de gasto "
            "associados a R\\$ 1 a mais da variável. Sob o teorema da equivalência, $\\gamma_{\\text{transf.}} = \\gamma_Y$. "
            "$G$ = despesa total; $G^{c}$ = despesa corrente; $T$ = FPM + ITR + cotas de ICMS, IPVA e IPI-exportação + IOF-ouro; "
            "$T^{*}$ = $T$ sem a cota do ICMS. Correlação com $Y$ dentro do município: $T$ = %s; $T^{*}$ = %s; ICMS = %s. "
            "A cota do ICMS responde, em média, por %s das transferências incondicionais de Camaçari e %s das de Barreiras (2014--2023). "
            "Com 20 observações e erros autocorrelacionados (Durbin-Watson abaixo de 2), os erros-padrão tendem a ser "
            "subestimados; os resultados são exploratórios. Fonte: elaboração própria.")
           % (ANO_BASE, br(corr["T"], 2), br(corr["Ts"], 2), br(corr["ICMS"], 2),
              pct(icms_share.get("Camaçari"), 0), pct(icms_share.get("Barreiras"), 0)),
           alinhamento="l" + "c" * len(res6))
pd.DataFrame([{"modelo": z["modelo"], "dependente": z["dep"], "regressores": "+".join(z["regs"]), "n": z["r"]["n"],
               "r2": z["r"]["r2"], "dw": z["r"]["dw"], **{f"b_{c}": v for c, v in z["r"]["b"].items()},
               **{f"ep_{c}": v for c, v in z["r"]["ep"].items()}, "dif_transf_Y": z["dif"], "ep_dif": z["ep_d"],
               "p_dif": z["p_d"], "p_fpm_igual_icms": z["p_fi"]} for z in res6]).to_csv(
    os.path.join(RES, "regressoes.csv"), index=False, encoding="utf-8-sig")

# Tabela 7: robustez e placebos (coeficiente da medida de transferência e p da igualdade com o PIB)
def linha_rob(rotulo, dados, regs, extra=("D",), alvo="Ts", pesos=None):
    cel = [rotulo]; reg = {"especificacao": rotulo}
    for dep in ["G", "Gc"]:
        r, d = fe(dados, dep, regs, extra)
        if pesos is None:
            est, ep = r["b"][alvo], r["ep"][alvo]; p = comb(r, {alvo: 1, "Y": -1})[2]
        else:
            est, ep, _ = comb(r, pesos(d, dep, 1)); p = comb(r, pesos(d, dep, 0))[2]
        cel += [br(est, 2) + " (" + br(ep, 2) + ")", br(p, 3)]
        reg.update({f"{dep}_coef": est, f"{dep}_ep": ep, f"{dep}_p_dif": p, f"{dep}_n": r["n"]})
    return cel, reg


rob, rob_csv = [], []
def add(*a, **k):
    c_, r_c = linha_rob(*a, **k); rob.append(c_); rob_csv.append(r_c)


add("Base: $T^{*}$ (Tabela~\\ref{tab:regressao})", amp, ["Ts", "Y"])
add("$T$ (com a cota do ICMS)", amp, ["T", "Y"], alvo="T")
add("Sem a dummy $D2018$", amp, ["Ts", "Y"], extra=())
add("Com tendência linear comum", amp, ["Ts", "Y"], extra=("D", "tend"))
for ano_ex in (2017, 2020, 2022):
    add(f"Sem o ano de {ano_ex}", amp[amp.ano != ano_ex], ["Ts", "Y"])
# totais em logaritmo com ln(pop): efeito marginal pelo método delta
tot = amp.copy()
for c in ["G", "Gc", "Ts", "Y"]:
    tot["ln" + c] = np.log(tot[c] * tot.populacao)
tot["lnpop"] = np.log(tot.populacao)
def peso_tot(d, dep, so_t):
    Gm = (d[dep] * d.populacao).mean()
    wT = Gm / (d.Ts * d.populacao).mean(); wY = Gm / (d.Y * d.populacao).mean()
    return {"lnTs": wT} if so_t else {"lnTs": wT, "lnY": -wY}
cel = ["Totais em log, com ln(população)$^{a}$"]; reg = {"especificacao": "totais"}
for dep in ["G", "Gc"]:
    r, d = fe(tot, "ln" + dep, ["lnTs", "lnY"], extra=("lnpop", "D"))
    est, ep, _ = comb(r, peso_tot(d, dep, 1)); p = comb(r, peso_tot(d, dep, 0))[2]
    cel += [br(est, 2) + " (" + br(ep, 2) + ")", br(p, 3)]; reg.update({f"{dep}_coef": est, f"{dep}_ep": ep, f"{dep}_p_dif": p})
rob.append(cel); rob_csv.append(reg)
# per capita em log, efeito marginal pelo método delta
lg = amp.copy()
for c in ["G", "Gc", "Ts", "Y"]:
    lg["ln" + c] = np.log(lg[c])
cel = ["Per capita em log$^{a}$"]; reg = {"especificacao": "log per capita"}
for dep in ["G", "Gc"]:
    r, d = fe(lg, "ln" + dep, ["lnTs", "lnY"])
    Gm = d[dep].mean(); wT = Gm / d.Ts.mean(); wY = Gm / d.Y.mean()
    est, ep, _ = comb(r, {"lnTs": wT}); p = comb(r, {"lnTs": wT, "lnY": -wY})[2]
    cel += [br(est, 2) + " (" + br(ep, 2) + ")", br(p, 3)]; reg.update({f"{dep}_coef": est, f"{dep}_ep": ep, f"{dep}_p_dif": p})
rob.append(cel); rob_csv.append(reg)
# inclinação diferente por município
cel_c, cel_b = ["Inclinação própria: Camaçari"], ["Inclinação própria: Barreiras"]; reg = {"especificacao": "interacao"}
p_int = {}
for dep in ["G", "Gc"]:
    r, d = fe(amp, dep, ["Ts", "Ts_bar", "Y"])
    est, ep, _ = comb(r, {"Ts": 1}); p = comb(r, {"Ts": 1, "Y": -1})[2]
    cel_c += [br(est, 2) + " (" + br(ep, 2) + ")", br(p, 3)]
    est, ep, _ = comb(r, {"Ts": 1, "Ts_bar": 1}); p = comb(r, {"Ts": 1, "Ts_bar": 1, "Y": -1})[2]
    cel_b += [br(est, 2) + " (" + br(ep, 2) + ")", br(p, 3)]
    p_int[dep] = r["p"]["Ts_bar"]; reg.update({f"{dep}_p_interacao": p_int[dep], f"{dep}_b_cam": r["b"]["Ts"],
                                              f"{dep}_b_bar": r["b"]["Ts"] + r["b"]["Ts_bar"]})
rob += [cel_c, cel_b]; rob_csv.append(reg)
rob.append("\\midrule")
add("Placebo: FUNDEB no lugar de $T^{*}$", amp, ["FUNDEB", "Y"], alvo="FUNDEB")
add("Placebo: SUS no lugar de $T^{*}$", amp, ["SUS", "Y"], alvo="SUS")
pd.DataFrame(rob_csv).to_csv(os.path.join(RES, "robustez.csv"), index=False, encoding="utf-8-sig")
tabela_tex("tab_robustez.tex", "Robustez e placebos: efeito marginal da transferência sobre o gasto (2014--2023)",
           "tab:robustez", ["Especificação", "Coef. (EP)", "$p$", "Coef. (EP)", "$p$"], rob,
           ("Nota: cada linha reestima o modelo da Tabela~\\ref{tab:regressao} com a alteração indicada; colunas 2--3 para a despesa total ($G$) "
            "e 4--5 para a despesa corrente ($G^{c}$). Coef. = reais de gasto por R\\$ 1 a mais da transferência indicada "
            "(EP HC1); $p$ = teste de igualdade com o efeito marginal do PIB. (a) Efeito marginal calculado pelo método delta "
            "a partir das elasticidades (coeficiente $\\times$ média do gasto / média da variável). Na especificação com "
            "inclinação própria, o $p$ da diferença entre os municípios é %s ($G$) e %s ($G^{c}$). Placebos: o FUNDEB e as "
            "transferências do SUS são vinculados, mas acompanham o mesmo ciclo de receitas; um coeficiente semelhante ao de "
            "$T^{*}$ indica que a associação não é específica das transferências incondicionais. Fonte: elaboração própria.")
           % (br(p_int["G"], 3), br(p_int["Gc"], 3)), alinhamento="lcccc")
f = os.path.join(TAB, "tab_robustez.tex"); s = open(f, encoding="utf-8").read()
s = s.replace("\\toprule\n", "\\toprule\n & \\multicolumn{2}{c}{Despesa total ($G$)} & \\multicolumn{2}{c}{Despesa corrente ($G^{c}$)} \\\\\n"
              "\\cmidrule(lr){2-3}\\cmidrule(lr){4-5}\n", 1)
open(f, "w", encoding="utf-8").write(s)
for velho in ("tab_regressao_decomposicao.tex",):
    if os.path.exists(os.path.join(TAB, velho)):
        os.remove(os.path.join(TAB, velho))

# Tabela: FPM e população (base do desenho de pares)
fp = t[t.ano.between(2014, 2025)].pivot(index="ano", columns="municipio", values="rec_fpm") / 1e6
pp = t[t.ano.between(2014, 2025)].pivot(index="ano", columns="municipio", values="populacao")
linhas = [[str(a), br(fp.loc[a, "Barreiras"], 1), br(fp.loc[a, "Camaçari"], 1),
           br(100 * fp.loc[a, "Barreiras"] / fp.loc[a, "Camaçari"], 1) + "\\%", br(pp.loc[a, "Barreiras"]), br(pp.loc[a, "Camaçari"])]
          for a in fp.index]
tabela_tex("tab_fpm.tex", "FPM recebido e população: Barreiras e Camaçari (2014--2025)", "tab:fpm",
           ["Ano", "FPM Barreiras", "FPM Camaçari", "Barreiras/Camaçari", "Pop. Barreiras", "Pop. Camaçari"], linhas,
           ("Nota: FPM em R\\$ milhões correntes, todas as parcelas (Siconfi, DCA). População: estimativas anuais do IBGE, "
            "Censo 2022 em 2022 e interpolação em 2023. O coeficiente do FPM de cada ano é fixado pelo TCU com a estimativa "
            "populacional do ano anterior; a Lei Complementar n.º 165/2019 manteve, até o censo seguinte, os coeficientes de "
            "2018 dos municípios que perderiam coeficiente por causa das estimativas anuais. Fonte: elaboração própria com "
            "dados do Siconfi e do IBGE."), alinhamento="lrrrrr")

# Tabela: resultado orçamentário com e sem a dedução do FUNDEB
ro = t[t.ano.between(2014, 2025)].copy()
ro["ded"] = ro.ded_fundeb_total.abs()
linhas = []
for a in range(2014, 2026):
    cel = [str(a)]
    for m in MUN:
        x = ro[(ro.municipio == m) & (ro.ano == a)].iloc[0]
        marca = "$^{\\dagger}$" if (x.resultado_bruto_sem_deducao > 0 and x.resultado_orcamentario < 0) else ""
        cel += [br(x.resultado_bruto_sem_deducao / 1e6, 1), br(x.ded / 1e6, 1), br(x.resultado_orcamentario / 1e6, 1) + marca]
    linhas.append(cel)
ro[["municipio", "ano", "resultado_bruto_sem_deducao", "ded", "resultado_orcamentario"]].to_csv(
    os.path.join(RES, "resultado_orcamentario.csv"), index=False, encoding="utf-8-sig")
nd = {m: ro[(ro.municipio == m) & ro.ano.between(2014, 2023) & (ro.resultado_orcamentario < 0)].ano.tolist() for m in MUN}
tabela_tex("tab_resultado.tex", "Resultado orçamentário com e sem a dedução para o FUNDEB (R\\$ milhões correntes)",
           "tab:resultado", ["Ano", "Bruto", "Dedução", "Líquido", "Bruto", "Dedução", "Líquido"], linhas,
           ("Nota: Bruto = receita total bruta menos despesa empenhada, como no trabalho anterior; Líquido = receita total "
            "líquida da dedução para a formação do FUNDEB menos despesa empenhada. $\\dagger$ = superávit no cálculo bruto que "
            "vira déficit no líquido. Entre 2014 e 2023, o resultado líquido é negativo em %d anos em Barreiras (%s) e em %d em "
            "Camaçari (%s). O resultado da execução de um exercício não mede, isoladamente, a situação fiscal: não considera "
            "restos a pagar, disponibilidade de caixa nem superávits financeiros de exercícios anteriores. Fonte: elaboração "
            "própria com dados do Siconfi (DCA).") % (len(nd["Barreiras"]), ", ".join(map(str, nd["Barreiras"])),
                                                     len(nd["Camaçari"]), ", ".join(map(str, nd["Camaçari"]))),
           alinhamento="lrrrrrr")
f = os.path.join(TAB, "tab_resultado.tex"); s = open(f, encoding="utf-8").read()
s = s.replace("\\toprule\n", "\\toprule\n & \\multicolumn{3}{c}{Barreiras} & \\multicolumn{3}{c}{Camaçari} \\\\\n"
              "\\cmidrule(lr){2-4}\\cmidrule(lr){5-7}\n", 1)
open(f, "w", encoding="utf-8").write(s)

# ------------------------------------------------------------------ Tabela: Hungria
ANOS_H = [a for a in [2012, 2013, 2014, 2016, 2019, 2022, 2025] if a in h.index]
h["pib_mio_huf"] = h.loc_receita_mio_huf / h.loc_receita_pct_pib * 100
h["loc_transf_capital_pct_pib"] = 100 * h.loc_transf_capital_mio_huf / h.pib_mio_huf
h["loc_tc_sobre_rec_sem_cap"] = h.loc_transf_correntes_mio_huf / (h.loc_receita_mio_huf - h.loc_transf_capital_mio_huf)
IH = [("loc_despesa_pct_pib", "Despesa dos governos locais (\\% do PIB)", lambda x: br(x, 1)),
      ("loc_receita_pct_pib", "Receita dos governos locais (\\% do PIB)", lambda x: br(x, 1)),
      ("loc_despesa_sobre_despesa_gg", "Despesa local / desp. do gov. geral", pct),
      ("loc_transf_correntes_pct_pib", "Transf. correntes recebidas (\\% do PIB)", lambda x: br(x, 1)),
      ("loc_transf_capital_pct_pib", "Transf. de capital recebidas (\\% do PIB)", lambda x: br(x, 1)),
      ("loc_impostos_pct_pib", "Impostos locais (\\% do PIB)", lambda x: br(x, 1)),
      ("loc_tc_sobre_rec_sem_cap", "Transf. correntes / receita sem transf. de capital", pct),
      ("loc_transf_total_sobre_receita", "Transf. correntes e de capital / receita", pct),
      ("loc_despesa_huf_real_pc", "Despesa local per capita (mil HUF de %d)" % ANO_BASE, lambda x: br(x / 1000, 0))]
linhas = [[rot] + [fmt(h.loc[a, v]) for a in ANOS_H] for v, rot, fmt in IH]
h[[v for v, _, _ in IH]].to_csv(os.path.join(RES, "indicadores_hungria.csv"), encoding="utf-8-sig")
tabela_tex("tab_hungria.tex", "Hungria: tamanho e financiamento dos governos locais (setor S1313)", "tab:hungria",
           ["Indicador"] + [str(a) for a in ANOS_H], linhas,
           ("Nota: governos locais = setor S1313 das contas nacionais (SEC 2010). Transferências correntes = D73 (dentro do governo "
            "geral); de capital = D9 (em 2013--2014 inclui a assunção das dívidas municipais pelo governo central); impostos = D2 + D5 + D91. "
            "Período: 2012--2025; a série obtida começa já dentro da primeira onda de recentralização. Valores reais deflacionados pelo HICP médio anual (preços de %d) e "
            "divididos pela população (Banco Mundial). Fonte: elaboração própria com dados do Eurostat (gov\\_10a\\_main, "
            "prc\\_hicp\\_aind) e do Banco Mundial.") % ANO_BASE, alinhamento="l" + "r" * len(ANOS_H))

# ------------------------------------------------------------------ Tabela: o que mudou em relação à P1
c = pd.read_csv(os.path.join("data", "registro_alteracoes", "comparacao_P1_P2.csv"))
ch = pd.read_csv(os.path.join("data", "registro_alteracoes", "hungria_P1_P2.csv"))
alt = c[c.tipo != "IGUAL"]
def faixa(sub):
    anos = sorted(sub.ano.unique()); return f"{anos[0]}--{anos[-1]}" if len(anos) > 1 and anos[-1] - anos[0] == len(anos) - 1 else ", ".join(map(str, anos))
L = []
g = alt[alt.variavel_P1 == "Receita_Total"]
if len(g): L.append(["Receita total (Camaçari)", faixa(g), "A base original excluía as receitas intraorçamentárias, mas não as despesas",
                     f"+{br(100 * g.dif_rel.min(), 1)} a +{br(100 * g.dif_rel.max(), 1)}\\%"])
g = alt[alt.variavel_P1 == "FPM"]
if len(g): L.append(["FPM", ", ".join(f"{m[:3]}. {a}" for m, a in zip(g.municipio, g.ano)), "A base original omitia as parcelas de 1\\%",
                     f"+{br(100 * g.dif_rel.min(), 1)} a +{br(100 * g.dif_rel.max(), 1)}\\%"])
g = alt[alt.variavel_P1 == "Funcao_Saude"]
if len(g): L.append(["Despesa em saúde (Camaçari)", faixa(g), "A base original registrava zero; valor da DCA: R\\$ %s mi" % br(g.valor_P2.iloc[0] / 1e6, 1), "--"])
g = alt[(alt.variavel_P1 == "População") & (alt.tipo == "CORRIGIDO")]
if len(g): L.append(["População (Barreiras)", faixa(g), "Erro de digitação na base original (%s; IBGE: %s)" % (br(g.valor_P1.iloc[0]), br(g.valor_P2.iloc[0])),
                     f"{br(100 * g.dif_rel.iloc[0], 1)}\\%"])
g = alt[alt.tipo == "PREENCHIDO"]
if len(g): L.append(["População", "2022--2023", "Ausente na base original; Censo 2022 e interpolação", "--"])
rr = t[t.ano.between(2014, 2023)]
vira = rr[(rr.resultado_bruto_sem_deducao > 0) & (rr.resultado_orcamentario < 0)]
L.append(["Resultado orçamentário", "2014--2023", "A base original não descontava a dedução do FUNDEB da receita (R\\$ %s a %s mi/ano); "
          "superávit vira déficit em %d município-anos (%s); ver Tabela~\\ref{tab:resultado}" % (br(rr.ded_fundeb_total.min() / 1e6, 0), br(rr.ded_fundeb_total.max() / 1e6, 0),
          len(vira), ", ".join(f"{m[:3]}. {a}" for m, a in zip(vira.municipio, vira.ano))), "--"])
L.append(["Despesa por função", "vários", "Zeros da base original tratados como ausentes", "--"])
L.append(["Hungria: receita e despesa do gov. geral", "2014--2021", "A base original trazia estimativas em HUF; a atualização usa o valor oficial do Eurostat",
          f"{br(100 * ch.dif_rel.min(), 1)} a +{br(100 * ch.dif_rel.max(), 1)}\\%"])
L.append(["Ampliações", "2014--2025", "2024--2025; ITR, IPVA, IPI, SUS, deduções do FUNDEB; governos locais húngaros", "--"])
iguais = (c.tipo == "IGUAL").sum(); total = len(c)
tabela_tex("tab_alteracoes.tex", "Principais alterações em relação ao trabalho anterior (2014--2023)", "tab:alteracoes",
           ["Variável", "Anos", "Alteração", "Diferença"], L,
           (f"Nota: dos {total} valores municipais comparáveis (17 variáveis, 2 municípios, 2014--2023), {iguais} coincidem com a base original "
            "(diferença menor que 0,1\\%). Diferença = (valor novo $-$ valor original)/valor original. Registro completo em data/registro\\_alteracoes/. "
            "Fonte: elaboração própria."), alinhamento="p{3.3cm}p{2.1cm}p{6.2cm}r")

# ------------------------------------------------------------------ Figuras
def rotulo_final(ax, x, y, txt, cor):
    """Marca o ponto final e guarda o rótulo; posiciona_rotulos() desenha sem sobreposição."""
    ax.plot([x], [y], "o", ms=4, color=cor)
    if not hasattr(ax, "_rotulos"):
        ax._rotulos = []
    ax._rotulos.append([x, y, txt])


def posiciona_rotulos(ax, folga=0.075):
    """Rótulos diretos no fim das linhas, afastados verticalmente (mín. `folga` da altura do eixo)."""
    r = sorted(getattr(ax, "_rotulos", []), key=lambda z: z[1])
    y0, y1 = ax.get_ylim(); gap = folga * (y1 - y0)
    pos = [z[1] for z in r]
    for i in range(1, len(pos)):
        pos[i] = max(pos[i], pos[i - 1] + gap)
    excesso = pos[-1] - (y1 - gap / 2) if pos else 0
    if excesso > 0:
        pos = [p - excesso for p in pos]
        for i in range(len(pos) - 2, -1, -1):
            pos[i] = min(pos[i], pos[i + 1] - gap)
    for (x, y, txt), yp in zip(r, pos):
        ax.annotate(txt, (x, y), xytext=(x + 0.35, yp), textcoords="data", va="center", fontsize=8, color=TINTA,
                    arrowprops=dict(arrowstyle="-", color=TINTA2, lw=0.5) if abs(yp - y) > gap * 0.3 else None)

# F1: FPM, cota de ICMS e impostos próprios per capita (small multiples, mesma escala)
FON = [("rec_fpm_real_pc", "FPM", "#2a78d6"), ("rec_icms_cota_real_pc", "Cota ICMS", "#eb6834"),
       ("impostos_proprios_real_pc", "Impostos próprios", "#1baf7a")]
fig, axs = plt.subplots(1, 2, figsize=(7.2, 3.0), sharey=True)
for ax, m in zip(axs, MUN):
    d = j[j.municipio == m]
    for v, rot, cor in FON:
        ax.plot(d.ano, d[v], color=cor, lw=2, marker="o", ms=3)
        rotulo_final(ax, d.ano.iloc[-1], d[v].iloc[-1], rot, cor)
    ax.set_title(m, fontsize=10, color=TINTA, loc="left")
    ax.set_xlim(A0 - 0.3, A1 + 2.6); ax.set_xticks(range(A0, A1 + 1, 3))
for ax in axs:
    posiciona_rotulos(ax)
axs[0].set_ylabel(f"R$ de {ANO_BASE} per capita")
axs[0].yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: br(x)))
fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig_fontes_receita.pdf")); fig.savefig(os.path.join(FIG, "fig_fontes_receita.png"), dpi=200)
plt.close(fig)

# F2: Hungria - tamanho (% do PIB) e financiamento (% da receita local), dois painéis (um eixo cada)
hh = h.loc[h.index >= 2012]  # inclui as colunas calculadas acima
fig, axs = plt.subplots(1, 2, figsize=(7.2, 3.0))
ax = axs[0]
for v, rot, cor in [("loc_despesa_pct_pib", "Despesa", "#2a78d6"), ("loc_receita_pct_pib", "Receita", "#eb6834")]:
    ax.plot(hh.index, hh[v], color=cor, lw=2, marker="o", ms=3); rotulo_final(ax, hh.index[-1], hh[v].iloc[-1], rot, cor)
ax.set_title("(a) Governos locais, % do PIB", fontsize=10, loc="left", color=TINTA); ax.set_ylim(0, None)
ax = axs[1]
for v, rot, cor in [("loc_transf_correntes_pct_pib", "Transf. correntes", "#2a78d6"),
                    ("loc_transf_capital_pct_pib", "Transf. de capital", "#eb6834"),
                    ("loc_impostos_pct_pib", "Impostos locais", "#1baf7a")]:
    ax.plot(hh.index, hh[v], color=cor, lw=2, marker="o", ms=3); rotulo_final(ax, hh.index[-1], hh[v].iloc[-1], rot, cor)
ax.set_title("(b) Receitas dos governos locais, % do PIB", fontsize=10, loc="left", color=TINTA); ax.set_ylim(0, None)
for ax in axs:
    ax.set_xlim(2011.6, 2025 + 3.4); ax.set_xticks(range(2012, 2026, 3)); ax.axvspan(2012.5, 2013.5, color=GRADE, alpha=0.6, lw=0)
    ax.text(2013, ax.get_ylim()[1] * 0.02, "2013", ha="center", va="bottom", fontsize=7, color=TINTA2)
    posiciona_rotulos(ax, folga=0.08)
fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig_hungria_local.pdf")); fig.savefig(os.path.join(FIG, "fig_hungria_local.png"), dpi=200)
plt.close(fig)

# (A antiga figura de dependência Brasil × Hungria foi retirada: as definições não são comparáveis em nível.)
for velho in ("fig_dependencia.pdf", "fig_dependencia.png"):
    if os.path.exists(os.path.join(FIG, velho)):
        os.remove(os.path.join(FIG, velho))

# ------------------------------------------------------------------ resumo no console
print(pd.read_csv(os.path.join(RES, "regressoes.csv")).round(3).to_string(index=False))
print(pd.read_csv(os.path.join(RES, "robustez.csv")).round(3).to_string(index=False))
print("Arquivos:", sorted(os.listdir(TAB)), sorted(os.listdir(FIG)))
