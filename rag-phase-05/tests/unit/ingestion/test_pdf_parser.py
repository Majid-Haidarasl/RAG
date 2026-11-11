from pathlib import Path

import pytest

from rag_core.ingestion.infrastructure.parser_pdf import parse_pdf
from tests.fixtures.ingestion.builders import write_scanned_pdf, write_text_pdf

pytestmark = pytest.mark.ingestion


def test_text_pdf_extracts_digital_layer(tmp_path: Path) -> None:
    path = write_text_pdf(tmp_path / "AR-SW-022-sla.pdf")
    blocks, scanned, pages = parse_pdf(path)
    assert pages == 1
    assert scanned == ()
    blob = "\n".join(b.text for b in blocks)
    assert "30 minutes" in blob
    assert "AR-SW-022" in blob


def test_image_only_pdf_is_flagged_as_scanned_and_not_ocred(tmp_path: Path) -> None:
    path = write_scanned_pdf(tmp_path / "AR-SW-022-scan.pdf")
    blocks, scanned, pages = parse_pdf(path)
    assert pages == 1
    assert scanned == (1,)
    # Detection only: we do not invent OCR text.
    text = "\n".join(b.text for b in blocks).strip()
    assert text == ""
