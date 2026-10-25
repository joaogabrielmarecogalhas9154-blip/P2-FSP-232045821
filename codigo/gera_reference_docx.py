"""Cria o documento de referência do pandoc (estilos do Word) no padrão ABNT.

Times New Roman 12, espaçamento 1,5, recuo de 1,25 cm, texto justificado,
margens de 3 cm (superior e esquerda) e 2 cm (inferior e direita), papel A4.
Uso: python3 gera_reference_docx.py saida.docx
"""
import subprocess
import sys

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

saida = sys.argv[1]
with open(saida, "wb") as f:
    f.write(subprocess.run(["pandoc", "--print-default-data-file", "reference.docx"],
                           check=True, capture_output=True).stdout)

doc = Document(saida)
FONTE = "Times New Roman"


def fonte(style, tam=12, negrito=None, italico=None, cor_preta=True):
    style.font.name = FONTE
    style.font.size = Pt(tam)
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = rpr.makeelement(qn("w:rFonts"), {})
        rpr.append(rfonts)
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(a), FONTE)
    for a in ("w:asciiTheme", "w:hAnsiTheme", "w:cstheme", "w:eastAsiaTheme"):
        if rfonts.get(qn(a)) is not None:
            del rfonts.attrib[qn(a)]
    if negrito is not None:
        style.font.bold = negrito
    if italico is not None:
        style.font.italic = italico
    if cor_preta:
        style.font.color.rgb = RGBColor(0, 0, 0)


def paragrafo(style, alinh=WD_ALIGN_PARAGRAPH.JUSTIFY, recuo=1.25, esp=1.5, antes=0, depois=0):
    pf = style.paragraph_format
    pf.alignment = alinh
    pf.first_line_indent = Cm(recuo) if recuo else Cm(0)
    pf.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE if esp == 1.5 else WD_LINE_SPACING.SINGLE
    pf.space_before = Pt(antes)
    pf.space_after = Pt(depois)


class _Estilos:
    """Busca estilos pelo nome gravado no XML (o pandoc usa 'Heading 1')."""

    def __init__(self, styles):
        self.styles = styles

    def __getitem__(self, nome):
        for st in self.styles:
            if st.element.name_val == nome or st.name == nome:
                return st
        raise KeyError(nome)

    def add_style(self, *a, **k):
        return self.styles.add_style(*a, **k)


estilos = _Estilos(doc.styles)
for nome in ("Normal", "Body Text", "First Paragraph", "Compact"):
    try:
        st = estilos[nome]
    except KeyError:
        continue
    fonte(st)
    paragrafo(st)
paragrafo(estilos["Compact"], recuo=0, esp=1)

for nome, tam in (("Heading 1", 12), ("Heading 2", 12), ("Heading 3", 12)):
    st = estilos[nome]
    fonte(st, tam, negrito=True, italico=False)
    paragrafo(st, alinh=WD_ALIGN_PARAGRAPH.LEFT, recuo=0, esp=1.5, antes=12, depois=6)

for nome in ("Title", "Subtitle", "Author", "Date", "Abstract"):
    try:
        st = estilos[nome]
    except KeyError:
        continue
    fonte(st, 12)
    paragrafo(st, alinh=WD_ALIGN_PARAGRAPH.CENTER, recuo=0, esp=1)

for nome in ("Caption", "Table Caption", "Image Caption"):
    try:
        st = estilos[nome]
    except KeyError:
        continue
    fonte(st, 10, italico=False)
    paragrafo(st, alinh=WD_ALIGN_PARAGRAPH.CENTER, recuo=0, esp=1, antes=6, depois=6)


def novo(nome, tam, alinh, recuo, esp, antes=0, depois=0, deslocamento=None):
    try:
        st = estilos[nome]
    except KeyError:
        st = estilos.add_style(nome, WD_STYLE_TYPE.PARAGRAPH)
    st.base_style = estilos["Normal"]
    fonte(st, tam)
    paragrafo(st, alinh, recuo, esp, antes, depois)
    if deslocamento:
        st.paragraph_format.left_indent = Cm(deslocamento)
        st.paragraph_format.first_line_indent = Cm(-deslocamento)
    return st


novo("Nota", 10, WD_ALIGN_PARAGRAPH.JUSTIFY, 0, 1, 2, 10)
novo("Referencia", 11, WD_ALIGN_PARAGRAPH.LEFT, 0, 1, 0, 8)
novo("Esquerda", 12, WD_ALIGN_PARAGRAPH.LEFT, 0, 1.5, 0, 0)
novo("Centralizado", 12, WD_ALIGN_PARAGRAPH.CENTER, 0, 1.5, 6, 6)
novo("Capa", 12, WD_ALIGN_PARAGRAPH.CENTER, 0, 1.5, 0, 0)

# sumário: estilos que o Word usa ao atualizar o campo (toc 1, toc 2)
from docx.enum.text import WD_TAB_ALIGNMENT, WD_TAB_LEADER  # noqa: E402

for nome, negrito, recuo in (("toc 1", True, 0), ("toc 2", False, 0.6)):
    st = novo(nome, 12, WD_ALIGN_PARAGRAPH.LEFT, 0, 1, 0, 4)
    st.font.bold = negrito
    st.paragraph_format.left_indent = Cm(recuo)
    st.paragraph_format.tab_stops.add_tab_stop(Cm(16), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)

for sec in doc.sections:
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.top_margin, sec.left_margin = Cm(3), Cm(3)
    sec.bottom_margin, sec.right_margin = Cm(2), Cm(2)

doc.save(saida)
