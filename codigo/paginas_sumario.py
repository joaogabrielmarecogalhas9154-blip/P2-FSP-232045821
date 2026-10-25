"""Preenche os números de página do sumário do .docx.

O sumário é um campo do Word já preenchido com os títulos. Para que ele abra com
as páginas certas, o script converte o .docx em PDF com o LibreOffice, procura em
que página cada título aparece e grava esses números no campo. No Word, basta
clicar com o botão direito no sumário e escolher "Atualizar campo" para recalcular.
Uso: python3 paginas_sumario.py arquivo.docx
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from docx import Document

arq = Path(sys.argv[1]).resolve()


def norm(t):
    return re.sub(r"\s+", " ", t).strip()


with tempfile.TemporaryDirectory() as tmp:
    try:
        subprocess.run(["soffice", "--headless", "--convert-to", "pdf", str(arq), "--outdir", tmp],
                       check=True, capture_output=True, timeout=300)
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        sys.exit("LibreOffice indisponível: atualize o sumário no Word (botão direito > Atualizar campo).")
    pdf = Path(tmp) / (arq.stem + ".pdf")
    texto = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], check=True, capture_output=True,
                           text=True).stdout

paginas = texto.split("\f")
doc = Document(str(arq))
faltando = []
for p in doc.paragraphs:
    if p.style.name not in ("toc 1", "toc 2"):
        continue
    corridas = [r for r in p.runs if r.text]
    titulo = norm("".join(r.text for r in corridas[:-1]))
    alvo = titulo[:45]
    pagina = None
    for i, pag in enumerate(paginas[2:], start=3):
        if any(norm(linha).startswith(alvo) for linha in pag.splitlines()):
            pagina = i
            break
    if pagina is None:
        faltando.append(titulo)
        continue
    corridas[-1].text = str(pagina)

doc.save(str(arq))
if faltando:
    print("Títulos não localizados:", faltando)
else:
    print("Sumário com páginas preenchidas.")
