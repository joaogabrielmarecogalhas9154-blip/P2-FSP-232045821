"""Ajustes finais no .docx gerado pelo pandoc: tabelas em estilo booktabs
(linhas só no topo, abaixo do cabeçalho e no fim), fonte 9 pt nas tabelas,
espaçamento simples nas células e numeração de páginas no rodapé.
Uso: python3 ajusta_docx.py arquivo.docx
"""
import copy
import re
import sys

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

arq = sys.argv[1]
doc = Document(arq)
LARGURA = 9072  # 16 cm de área útil, em twips
MINIMO = 850  # 1,5 cm


def borda(cell, lado, tam=8):
    tcPr = cell._tc.get_or_add_tcPr()
    bordas = tcPr.find(qn("w:tcBorders"))
    if bordas is None:
        bordas = OxmlElement("w:tcBorders")
        tcPr.append(bordas)
    b = OxmlElement(f"w:{lado}")
    b.set(qn("w:val"), "single")
    b.set(qn("w:sz"), str(tam))
    b.set(qn("w:space"), "0")
    b.set(qn("w:color"), "000000")
    bordas.append(b)


for t in doc.tables:
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    tblPr = t._tbl.tblPr
    # remove bordas do estilo e usa largura automática a 100%
    for el in tblPr.findall(qn("w:tblBorders")):
        tblPr.remove(el)
    w = tblPr.find(qn("w:tblW"))
    if w is None:
        w = OxmlElement("w:tblW")
        tblPr.append(w)
    w.set(qn("w:type"), "dxa")
    w.set(qn("w:w"), str(LARGURA))
    linhas = t.rows
    # larguras proporcionais ao texto de cada coluna (layout fixo)
    ncol = len(t.columns)
    pesos = []
    for j in range(ncol):
        tam = [len(row.cells[j].text.strip()) for row in linhas if j < len(row.cells)]
        pesos.append(max(4, min(55, max(tam) if tam else 4)))
    # colunas de texto longo ficam alinhadas à esquerda; numéricas, centralizadas
    texto_longo = []
    for j in range(ncol):
        tam = [len(row.cells[j].text.strip()) for row in linhas[1:] if j < len(row.cells)]
        texto_longo.append(bool(tam) and sum(tam) / len(tam) > 22)
    total = sum(pesos)
    larg = [max(MINIMO, int(LARGURA * p / total)) for p in pesos]
    excesso = sum(larg) - LARGURA
    if excesso > 0:
        k = larg.index(max(larg))
        larg[k] -= excesso
    lay = tblPr.find(qn("w:tblLayout"))
    if lay is None:
        lay = OxmlElement("w:tblLayout")
        tblPr.append(lay)
    lay.set(qn("w:type"), "fixed")
    grid = t._tbl.tblGrid
    for j, gc in enumerate(grid.findall(qn("w:gridCol"))):
        gc.set(qn("w:w"), str(larg[j]))
    for row in linhas:
        idx = 0
        for tc in row._tr.tc_lst:
            span = tc.grid_span
            tcPr = tc.get_or_add_tcPr()
            tcw = tcPr.find(qn("w:tcW"))
            if tcw is None:
                tcw = OxmlElement("w:tcW")
                tcPr.insert(0, tcw)
            tcw.set(qn("w:type"), "dxa")
            tcw.set(qn("w:w"), str(sum(larg[idx:idx + span])))
            idx += span
    for i, row in enumerate(linhas):
        for j, cell in enumerate(row.cells):
            for p in cell.paragraphs:
                pf = p.paragraph_format
                pf.first_line_indent = Cm(0)
                pf.line_spacing_rule = WD_LINE_SPACING.SINGLE
                pf.space_before = Pt(1)
                pf.space_after = Pt(1)
                if j > 0 and not texto_longo[j]:
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                else:
                    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                for r in p.runs:
                    r.font.size = Pt(9)
                    r.font.name = "Times New Roman"
            if i == 0:
                borda(cell, "top", 12)
            if i == len(linhas) - 1:
                borda(cell, "bottom", 12)
    # linha abaixo do cabeçalho (primeira linha marcada como cabeçalho pelo pandoc)
    cab = [r for r in linhas if r._tr.trPr is not None and r._tr.trPr.find(qn("w:tblHeader")) is not None]
    alvo = cab[-1] if cab else linhas[0]
    for cell in alvo.cells:
        borda(cell, "bottom", 6)

# imagens centralizadas e sem recuo
for p in doc.paragraphs:
    if p._p.findall(".//" + qn("w:drawing")):
        p.paragraph_format.first_line_indent = Cm(0)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

def campo(run, tipo):
    fc = OxmlElement("w:fldChar")
    fc.set(qn("w:fldCharType"), tipo)
    run._r.append(fc)


def instr(run, texto):
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = texto
    run._r.append(it)


def nome_estilo(p):
    ps = p._p.pPr.find(qn("w:pStyle")) if p._p.pPr is not None else None
    return ps.get(qn("w:val")) if ps is not None else ""


# títulos: número e texto separados por espaço (e não por tabulação)
titulos = []
for p in doc.paragraphs:
    est = nome_estilo(p)
    if est in ("Heading1", "Heading2"):
        for r in p._p.findall(qn("w:r")):
            tab = r.find(qn("w:tab"))
            if tab is not None:
                t = OxmlElement("w:t")
                t.set(qn("xml:space"), "preserve")
                t.text = " "
                r.replace(tab, t)
        texto = re.sub(r"\s+", " ", p.text).strip()
        titulos.append((1 if est == "Heading1" else 2, texto))

# capa: título no meio da folha e local/data no pé
for p in doc.paragraphs:
    if nome_estilo(p) != "Capa":
        continue
    if p.text.startswith("Dependência de transferências"):
        p.paragraph_format.space_before = Cm(6.5)
    elif p.text.startswith("Brasília,"):
        p.paragraph_format.space_before = Cm(7.5)
    elif p.text.startswith("João Gabriel"):
        p.paragraph_format.space_before = Cm(1)

# sumário: substitui o marcador por título + campo TOC já preenchido
marca = next(p for p in doc.paragraphs if p.text.strip() == "SUMARIOMARCA")
for r in marca.runs[1:]:
    r._r.getparent().remove(r._r)
marca.runs[0].text = "SUMÁRIO"
marca.runs[0].bold = True
marca.paragraph_format.page_break_before = True
marca.paragraph_format.space_after = Pt(12)

ancora = marca
entradas = []
for k, (nivel, texto) in enumerate(titulos):
    novo = OxmlElement("w:p")
    ancora._p.addnext(novo)
    from docx.text.paragraph import Paragraph
    par = Paragraph(novo, marca._parent)
    par.style = doc.styles["toc 1" if nivel == 1 else "toc 2"]
    if k == 0:
        r0 = par.add_run()
        campo(r0, "begin")
        instr(r0, ' TOC \\o "1-2" \\h \\z \\u ')
        campo(r0, "separate")
    par.add_run(texto)
    par.add_run("\t")
    par.add_run("0")
    entradas.append(par)
    ancora = par
fim = entradas[-1].add_run()
campo(fim, "end")

# quebra de seção depois do sumário: capa e sumário sem número de página
corpo_sect = doc.element.body.find(qn("w:sectPr"))
sect = copy.deepcopy(corpo_sect)
for el in list(sect):
    if el.tag in (qn("w:headerReference"), qn("w:footerReference"), qn("w:titlePg")):
        sect.remove(el)
entradas[-1]._p.get_or_add_pPr().append(sect)

# número de página no rodapé (só na seção do texto; a contagem inclui capa e sumário)
sec = doc.sections[-1]
rodape = sec.footer
rodape.is_linked_to_previous = False
p = rodape.paragraphs[0] if rodape.paragraphs else rodape.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
run = p.add_run()
campo(run, "begin")
instr(run, "PAGE")
campo(run, "end")

doc.save(arq)
