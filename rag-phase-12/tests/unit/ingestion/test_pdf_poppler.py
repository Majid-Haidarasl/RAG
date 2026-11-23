"""Poppler pdftotext adapter: RTL reconstruction (pure) and real binary (skip if missing)."""

from pathlib import Path
import subprocess

import pytest

from rag_core.ingestion.domain.errors import GarbledTextError
from rag_core.ingestion.infrastructure import pdf_poppler
from rag_core.ingestion.infrastructure.parser_doc import find_soffice
from rag_core.ingestion.infrastructure.parser_pdf import parse_pdf, parse_pdf_detailed
from rag_core.ingestion.infrastructure.pdf_poppler import (
    Box,
    PopplerPage,
    line_text,
    parse_bbox_pages,
    repair_single_letters,
    visual_to_logical,
)
from rag_core.knowledge.domain.fingerprint import char_shingles, containment
from tests.fixtures.ingestion.builders import PERSIAN_PARAGRAPHS, write_persian_docx, write_text_pdf

pytestmark = pytest.mark.ingestion

HAS_PDFTOTEXT = pdf_poppler.find_pdftotext() is not None


def test_visual_run_is_reversed_but_numbers_keep_direction() -> None:
    assert visual_to_logical("بوصم") == "مصوب"
    assert visual_to_logical("۱۴۰۳ رهم") == "مهر ۱۴۰۳"


def test_single_letters_are_reattached() -> None:
    assert repair_single_letters("ت صمیم و خ دمت") == "تصمیم و خدمت"
    assert repair_single_letters("نتیج ه مجاز") == "نتیجه مجاز"
    assert repair_single_letters("کار و حضور") == "کار و حضور"  # و is a real word


def test_rtl_line_joins_small_gaps_and_keeps_real_spaces() -> None:
    h = 20.0
    # visual right-to-left: "دان" "ش" (tiny gap → one word) then real space, then "مصوب"
    boxes = [
        Box(391.6, 0, 401.1, h, "ناد"),
        Box(386.2, 0, 391.0, h, "ش"),       # gap 0.6/20 = 0.03 < join gap
        Box(350.0, 0, 383.8, h, "بوصم"),    # gap 2.4/20 = 0.12 → space
    ]
    assert line_text(boxes, join_gap=0.066) == "دانش مصوب"


def test_ltr_run_inside_rtl_line_keeps_its_order() -> None:
    h = 20.0
    boxes = [
        Box(400, 0, 440, h, "خیرات"),       # تاریخ
        Box(350, 0, 390, h, "یداتسرف"),     # فرستادی
        Box(200, 0, 240, h, "October"),
        Box(250, 0, 290, h, "2024"),
    ]
    assert line_text(boxes, join_gap=0.066) == "تاریخ فرستادی October 2024"


def test_bbox_xhtml_is_parsed_and_bidi_marks_removed() -> None:
    xhtml = '<page width="595" height="842"><word xMin="1" yMin="2" xMax="3" yMax="4">\u202bبوصم\u202c</word></page>'
    pages = parse_bbox_pages(xhtml)
    assert pages == [[Box(1.0, 2.0, 3.0, 4.0, "بوصم")]]


def test_forced_pdfplumber_fallback_reports_install_hint(tmp_path: Path) -> None:
    path = write_text_pdf(tmp_path / "AR-SW-022-sla.pdf")
    result = parse_pdf_detailed(path, pdftotext=False)
    assert result.engine == "pdfplumber"
    assert any("sudo apt install -y poppler-utils" in w for w in result.warnings)


def test_garbled_text_is_a_failure_not_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = write_text_pdf(tmp_path / "AR-SW-022-sla.pdf")
    garbled = " ".join(["(cid:11)ش", "هرود", "(cid:22)ئ"] * 30)
    monkeypatch.setattr(
        pdf_poppler, "extract_pdf_pages", lambda p, exe=None: ([PopplerPage(1, (garbled,))], {})
    )
    with pytest.raises(GarbledTextError, match="garbled text from pdftotext"):
        parse_pdf_detailed(path, pdftotext="/usr/bin/pdftotext")


@pytest.mark.skipif(not HAS_PDFTOTEXT, reason="poppler pdftotext is not installed (sudo apt install -y poppler-utils)")
def test_pdftotext_is_primary_engine_for_text_pdf(tmp_path: Path) -> None:
    path = write_text_pdf(tmp_path / "AR-SW-022-sla.pdf")
    result = parse_pdf_detailed(path)
    assert result.engine == "pdftotext"
    blob = "\n".join(b.text for b in result.blocks)
    assert "30 minutes" in blob and "AR-SW-022" in blob
    assert result.quality.verdict == "ok"
    blocks, scanned, pages = parse_pdf(path)
    assert pages == 1 and scanned == ()


@pytest.mark.skipif(
    not HAS_PDFTOTEXT or find_soffice() is None,
    reason="needs poppler pdftotext and LibreOffice to render a Persian PDF",
)
def test_persian_pdf_comes_back_in_logical_order(tmp_path: Path) -> None:
    docx = write_persian_docx(tmp_path / "fa.docx")
    subprocess.run(
        [find_soffice(), f"-env:UserInstallation=file://{tmp_path / 'lo'}", "--headless",
         "--convert-to", "pdf", "--outdir", str(tmp_path), str(docx)],
        check=True, capture_output=True, timeout=180,
    )
    pdf = tmp_path / "fa.pdf"
    result = parse_pdf_detailed(pdf)
    text = "\n".join(b.text for b in result.blocks)
    assert result.engine == "pdftotext"
    assert not result.quality.is_garbled
    assert result.quality.metrics["function_words"] > result.quality.metrics["reversed_function_words"]
    source = char_shingles(" ".join(PERSIAN_PARAGRAPHS))
    assert containment(source, char_shingles(text)) >= 0.80
    assert "AR-HR-005" in text
