"""Small generated fixtures. Tests never open the real corpus."""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


def _outline(paragraph, level: int) -> None:
    pPr = paragraph._p.get_or_add_pPr()
    outline = OxmlElement("w:outlineLvl")
    outline.set(qn("w:val"), str(level))
    pPr.append(outline)


def write_sample_docx(path: Path) -> Path:
    """Heading, paragraph, table, paragraph — in that order — plus a Persian ID typo."""
    doc = Document()
    h = doc.add_paragraph("1. Leave policy")
    h.style = doc.styles["Heading 1"]
    doc.add_paragraph("Annual leave is 26 days. See AR-HR-۰۰۵ for the full table.")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Item"
    table.cell(0, 1).text = "Days"
    table.cell(1, 0).text = "Annual leave"
    table.cell(1, 1).text = "26"
    doc.add_paragraph("The table above is normative.")
    # A second heading + long-ish clause
    h2 = doc.add_paragraph("2. Identifiers")
    h2.style = doc.styles["Heading 1"]
    doc.add_paragraph("نسخه آزمايشي با حرف ي و ك عربي.")
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    return path


def write_ordered_docx(path: Path) -> Path:
    """Used to assert table position is between two known paragraphs."""
    doc = Document()
    doc.add_paragraph("BEFORE_TABLE")
    table = doc.add_table(rows=1, cols=1)
    table.cell(0, 0).text = "IN_TABLE"
    doc.add_paragraph("AFTER_TABLE")
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    return path


def write_long_clause_docx(path: Path, text: str) -> Path:
    doc = Document()
    h = doc.add_paragraph("Clause")
    h.style = doc.styles["Heading 1"]
    doc.add_paragraph(text)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    return path


def write_text_pdf(path: Path) -> Path:
    """A digital text PDF with a short table-like layout, no scan."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = b"""BT
/F1 12 Tf
72 720 Td
(AR-SW-022 Software SLA) Tj
0 -20 Td
(Priority 1 response time is 30 minutes.) Tj
ET
"""
    path.write_bytes(_minimal_text_pdf(content))
    return path


def _minimal_text_pdf(stream: bytes) -> bytes:
    # One-page PDF 1.4 with Helvetica and the given content stream.
    objects = []

    def obj(n: int, body: str) -> bytes:
        return f"{n} 0 obj\n{body}\nendobj\n".encode("latin-1")

    font = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    contents = f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1") + stream + b"\nendstream"
    page = "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
    pages = "<< /Type /Pages /Kids [3 0 R] /Count 1 >>"
    catalog = "<< /Type /Catalog /Pages 2 0 R >>"
    # numbers: 1 catalog, 2 pages, 3 page, 4 contents, 5 font
    parts = [
        b"%PDF-1.4\n",
        obj(1, catalog),
        obj(2, pages),
        obj(3, page),
        b"4 0 obj\n" + contents + b"\nendobj\n",
        obj(5, font),
    ]
    # xref
    buf = b"".join(parts)
    # rebuild with offsets
    header = b"%PDF-1.4\n"
    bodies = [
        obj(1, catalog),
        obj(2, pages),
        obj(3, page),
        b"4 0 obj\n" + contents + b"\nendobj\n",
        obj(5, font),
    ]
    out = header
    offsets = [0]
    for body in bodies:
        offsets.append(len(out))
        out += body
    xref_pos = len(out)
    xref = f"xref\n0 6\n0000000000 65535 f \n"
    for off in offsets[1:]:
        xref += f"{off:010d} 00000 n \n"
    start = xref + f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n"
    return out + start.encode("latin-1")


def write_scanned_pdf(path: Path) -> Path:
    """Image-only PDF (no text layer) used to test scan detection."""
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (200, 80), color=(240, 240, 240))
    img_path = path.with_suffix(".png")
    image.save(img_path)
    # Build a single-image PDF with Pillow.
    image.save(path, "PDF", resolution=72.0)
    return path


PERSIAN_PARAGRAPHS = (
    "این سیاست تصمیم مرخصی و حضور را قابل ردیابی می‌کند و همزمان تداوم خدمت و حریم خصوصی کارکنان را حفظ می‌کند.",
    "مدیر مستقیم پوشش کار را برنامه‌ریزی می‌کند و حسابداری نتیجه مجاز حضور را برای حقوق استفاده می‌کند.",
    "درخواست مرخصی باید پیش از شروع در سامانه ثبت شود و تأیید مدیر با تاریخ و ساعت نگهداری شود.",
    "شناسه سند AR-HR-005 است و نسخه ۱.۰ از مهر ۱۴۰۳ اعتبار دارد.",
)


def write_persian_docx(path: Path) -> Path:
    """Right-to-left Persian paragraphs (rendered to PDF by LibreOffice in tests)."""
    doc = Document()
    for text in PERSIAN_PARAGRAPHS:
        paragraph = doc.add_paragraph(text)
        pPr = paragraph._p.get_or_add_pPr()
        pPr.append(OxmlElement("w:bidi"))
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    return path
