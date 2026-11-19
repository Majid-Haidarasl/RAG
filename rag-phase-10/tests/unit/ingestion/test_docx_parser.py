from pathlib import Path

import pytest

from rag_core.ingestion.infrastructure.parser_docx import parse_docx
from tests.fixtures.ingestion.builders import write_ordered_docx, write_sample_docx

pytestmark = pytest.mark.ingestion


def test_docx_keeps_table_between_surrounding_paragraphs(tmp_path: Path) -> None:
    path = write_ordered_docx(tmp_path / "AR-ORG-001-order.docx")
    blocks = parse_docx(path)
    texts = [b.text for b in blocks]
    assert texts == ["BEFORE_TABLE", "IN_TABLE", "AFTER_TABLE"]
    assert blocks[1].kind.value == "table"


def test_docx_captures_heading_paragraph_and_table(tmp_path: Path) -> None:
    path = write_sample_docx(tmp_path / "fa" / "AR-HR-005-leave.docx")
    blocks = parse_docx(path)
    kinds = [b.kind.value for b in blocks]
    assert "heading" in kinds
    assert "table" in kinds
    table = next(b for b in blocks if b.kind.value == "table")
    assert "26" in table.text
    assert table.cells[0] == ("Item", "Days")
    assert any("AR-HR-۰۰۵" in b.text for b in blocks)
