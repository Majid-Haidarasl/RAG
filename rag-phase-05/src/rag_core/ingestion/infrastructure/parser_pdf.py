"""Text-PDF adapter using pdfplumber, plus scanned-page detection (no OCR)."""

from __future__ import annotations

from pathlib import Path

from rag_core.ingestion.domain.errors import ParseFailedError
from rag_core.ingestion.domain.model import BlockKind, ContentBlock

# A page with this little extractable text and at least one image is treated
# as a scan (or a blank cover). The threshold is conservative so a short
# heading-only page is not flagged if it has no image.
SCAN_CHAR_THRESHOLD = 40


def _page_is_scanned(page: object, text: str) -> bool:
    images = getattr(page, "images", None) or []
    chars = getattr(page, "chars", None) or []
    if len(text.strip()) >= SCAN_CHAR_THRESHOLD:
        return False
    if images:
        return True
    # Image-only pages sometimes expose no "images" list but also no chars.
    return len(chars) < 8 and len(text.strip()) < 8


def _tables_as_blocks(page: object, page_number: int, start_index: int) -> list[ContentBlock]:
    blocks: list[ContentBlock] = []
    try:
        tables = page.extract_tables() or []
    except Exception:  # noqa: BLE001
        tables = []
    for table_index, table in enumerate(tables):
        rows: list[tuple[str, ...]] = []
        for row in table or []:
            cells = tuple((cell or "").strip() if cell is not None else "" for cell in row)
            rows.append(cells)
        text = "\n".join(" | ".join(row) for row in rows).strip()
        if not text:
            continue
        blocks.append(
            ContentBlock(
                kind=BlockKind.TABLE,
                text=text,
                index=start_index + len(blocks),
                page=page_number,
                table_index=table_index,
                cells=tuple(rows),
            )
        )
    return blocks


def parse_pdf(path: Path) -> tuple[list[ContentBlock], tuple[int, ...], int]:
    """Return (blocks, scanned_page_numbers, page_count). Never runs OCR."""
    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover
        raise ParseFailedError(str(path), "pdfplumber is not installed") from exc

    blocks: list[ContentBlock] = []
    scanned: list[int] = []
    try:
        with pdfplumber.open(path) as pdf:
            page_count = len(pdf.pages)
            for number, page in enumerate(pdf.pages, start=1):
                try:
                    raw = page.extract_text() or ""
                except Exception as exc:  # noqa: BLE001
                    raise ParseFailedError(str(path), f"page {number}: {exc}") from exc
                text = raw.strip()
                if _page_is_scanned(page, text):
                    scanned.append(number)
                # Split kept text into paragraphs on blank lines, then append tables.
                if text:
                    for paragraph in [p.strip() for p in text.split("\n\n") if p.strip()]:
                        # pdfplumber often uses single newlines; also split long line groups
                        blocks.append(
                            ContentBlock(
                                kind=BlockKind.PARAGRAPH,
                                text=paragraph,
                                index=len(blocks),
                                page=number,
                                paragraph_index=len(blocks),
                            )
                        )
                for table_block in _tables_as_blocks(page, number, len(blocks)):
                    # Skip a table whose full text was already captured in the page text.
                    if table_block.text and table_block.text in text:
                        continue
                    blocks.append(
                        ContentBlock(
                            kind=table_block.kind,
                            text=table_block.text,
                            index=len(blocks),
                            page=number,
                            table_index=table_block.table_index,
                            cells=table_block.cells,
                        )
                    )
    except ParseFailedError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ParseFailedError(str(path), str(exc)) from exc
    return blocks, tuple(scanned), page_count
