"""Extra coverage for parser_pdf: scan detection, tables, fallbacks and error paths."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from rag_core.ingestion.domain.errors import GarbledTextError, ParseFailedError, POPPLER_INSTALL
from rag_core.ingestion.domain.model import BlockKind, ContentBlock
from rag_core.ingestion.domain.text_quality import TextQuality
from rag_core.ingestion.infrastructure import parser_pdf as mod
from rag_core.ingestion.infrastructure import pdf_poppler
from rag_core.ingestion.infrastructure.parser_pdf import (
    _append_tables,
    _page_is_scanned,
    _paragraph_blocks,
    _tables_as_blocks,
    parse_pdf,
    parse_pdf_detailed,
)
from tests.fixtures.ingestion.builders import write_text_pdf

pytestmark = pytest.mark.ingestion


def test_page_is_scanned_without_images_when_almost_empty() -> None:
    page = SimpleNamespace(images=[], chars=[1, 2, 3])
    assert _page_is_scanned(page, "hi") is True


def test_page_not_scanned_when_chars_exist_even_if_short_text() -> None:
    page = SimpleNamespace(images=None, chars=list(range(10)))
    assert _page_is_scanned(page, "short") is False


def test_page_scanned_with_image_and_little_text() -> None:
    page = SimpleNamespace(images=[{"width": 10}], chars=[])
    assert _page_is_scanned(page, "cover") is True


def test_page_not_scanned_when_text_passes_threshold() -> None:
    page = SimpleNamespace(images=[{"width": 10}], chars=[])
    assert _page_is_scanned(page, "x" * 50) is False


def test_tables_as_blocks_swallows_extract_error() -> None:
    page = SimpleNamespace(extract_tables=lambda: (_ for _ in ()).throw(RuntimeError("no tables")))
    assert _tables_as_blocks(page, 1, 0) == []


def test_tables_as_blocks_handles_none_cells_and_skips_empty() -> None:
    def extract_tables():
        return [
            None,
            [],
            [["A", None], [None, "B"]],
            [[]],
        ]

    page = SimpleNamespace(extract_tables=extract_tables)
    blocks = _tables_as_blocks(page, 3, 5)
    assert len(blocks) == 1
    assert blocks[0].kind == BlockKind.TABLE
    assert blocks[0].text == "A | \n | B"
    assert blocks[0].cells == (("A", ""), ("", "B"))
    assert blocks[0].index == 5
    assert blocks[0].page == 3
    assert blocks[0].table_index == 2


def test_paragraph_blocks_skips_blank_entries() -> None:
    blocks = _paragraph_blocks([(1, ["", "  ", "Hello Persian متن", "\n"])])
    assert len(blocks) == 1
    assert blocks[0].text == "Hello Persian متن"
    assert blocks[0].page == 1


def test_append_tables_keeps_novel_readable_table() -> None:
    blocks: list[ContentBlock] = []
    table = ContentBlock(
        kind=BlockKind.TABLE,
        text="ColA | ColB\n1 | 2",
        index=0,
        page=1,
        table_index=0,
        cells=(("ColA", "ColB"), ("1", "2")),
    )
    _append_tables(blocks, 1, [table], page_text="paragraph only")
    assert len(blocks) == 1
    assert blocks[0].text == table.text
    assert blocks[0].cells == table.cells


def test_append_tables_skips_duplicate_and_garbled() -> None:
    blocks: list[ContentBlock] = []
    dup = ContentBlock(kind=BlockKind.TABLE, text="already here", index=0, page=1)
    garbled = ContentBlock(
        kind=BlockKind.TABLE,
        text=" ".join(["(cid:11)"] * 40),
        index=1,
        page=1,
    )
    empty = ContentBlock(kind=BlockKind.TABLE, text="", index=2, page=1)
    _append_tables(blocks, 1, [dup, garbled, empty], page_text="prefix already here suffix")
    assert blocks == []


def test_pdftotext_failure_falls_back_to_pdfplumber(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = write_text_pdf(tmp_path / "AR-SW-022-sla.pdf")
    monkeypatch.setattr(
        pdf_poppler,
        "extract_pdf_pages",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("broken poppler")),
    )
    result = parse_pdf_detailed(path, pdftotext="/usr/bin/pdftotext")
    assert result.engine == "pdfplumber"
    assert any("pdftotext failed" in w and "broken poppler" in w for w in result.warnings)
    blob = "\n".join(b.text for b in result.blocks)
    assert "30 minutes" in blob or "AR-SW-022" in blob


def test_pdftotext_false_forces_fallback_warning(tmp_path: Path) -> None:
    path = write_text_pdf(tmp_path / "AR-SW-022-sla.pdf")
    result = parse_pdf_detailed(path, pdftotext=False)
    assert result.engine == "pdfplumber"
    assert any(POPPLER_INSTALL in w for w in result.warnings)


def test_extract_text_page_error_becomes_parse_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = write_text_pdf(tmp_path / "AR-SW-022-sla.pdf")

    class BadPage:
        images: list = []
        chars: list = list(range(20))

        def extract_text(self) -> str:
            raise ValueError("bad page text")

        def extract_tables(self):
            return []

    class BadPdf:
        pages = [BadPage()]

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    import pdfplumber

    monkeypatch.setattr(pdfplumber, "open", lambda _p: BadPdf())
    with pytest.raises(ParseFailedError, match="page 1: bad page text"):
        parse_pdf_detailed(path, pdftotext=False)


def test_open_failure_wrapped_as_parse_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = write_text_pdf(tmp_path / "AR-SW-022-sla.pdf")
    import pdfplumber

    monkeypatch.setattr(pdfplumber, "open", lambda _p: (_ for _ in ()).throw(OSError("cannot open")))
    with pytest.raises(ParseFailedError, match="cannot open"):
        parse_pdf_detailed(path, pdftotext=False)


def test_fragmented_quality_adds_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = write_text_pdf(tmp_path / "AR-SW-022-sla.pdf")
    monkeypatch.setattr(
        mod,
        "assess_text_quality",
        lambda _text: TextQuality("fragmented", ("too many fragments",), {"chars": 10.0}),
    )
    result = parse_pdf_detailed(path, pdftotext=False)
    assert any("fragmented PDF text: too many fragments" in w for w in result.warnings)


def test_garbled_pdfplumber_includes_poppler_hint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = write_text_pdf(tmp_path / "AR-SW-022-sla.pdf")
    monkeypatch.setattr(
        mod,
        "assess_text_quality",
        lambda _text: TextQuality("garbled", ("cid glyphs",), {}),
    )
    with pytest.raises(GarbledTextError, match="poppler"):
        parse_pdf_detailed(path, pdftotext=False)


def test_garbled_pdftotext_omits_install_hint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = write_text_pdf(tmp_path / "AR-SW-022-sla.pdf")
    monkeypatch.setattr(
        pdf_poppler,
        "extract_pdf_pages",
        lambda *_a, **_k: ([pdf_poppler.PopplerPage(1, ("hello world",))], {}),
    )
    monkeypatch.setattr(
        mod,
        "assess_text_quality",
        lambda _text: TextQuality("garbled", ("cid glyphs",), {}),
    )
    with pytest.raises(GarbledTextError) as excinfo:
        parse_pdf_detailed(path, pdftotext="/usr/bin/pdftotext")
    assert POPPLER_INSTALL not in str(excinfo.value)


def test_full_pipeline_appends_table_not_in_page_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = write_text_pdf(tmp_path / "AR-SW-022-sla.pdf")

    class TablePage:
        images: list = []
        chars: list = list(range(20))

        def extract_text(self) -> str:
            return "Body paragraph about SLA."

        def extract_tables(self):
            return [[["Metric", "Value"], ["P1", "30 minutes"]]]

    class TablePdf:
        pages = [TablePage()]

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    import pdfplumber

    monkeypatch.setattr(pdfplumber, "open", lambda _p: TablePdf())
    result = parse_pdf_detailed(path, pdftotext=False)
    kinds = [b.kind for b in result.blocks]
    assert BlockKind.PARAGRAPH in kinds
    assert BlockKind.TABLE in kinds
    table = next(b for b in result.blocks if b.kind == BlockKind.TABLE)
    assert "30 minutes" in table.text
    assert table.cells[0] == ("Metric", "Value")


def test_parse_pdf_wrapper_returns_tuple(tmp_path: Path) -> None:
    path = write_text_pdf(tmp_path / "AR-SW-022-sla.pdf")
    blocks, scanned, pages = parse_pdf(path)
    assert pages == 1
    assert isinstance(scanned, tuple)
    assert isinstance(blocks, list)
