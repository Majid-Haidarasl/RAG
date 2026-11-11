"""PDF adapter: poppler ``pdftotext`` for text, pdfplumber for geometry/tables.

Phase 5.1 fix: pdfplumber returned Persian PDFs as ``(cid:NN)`` placeholders in
visual order and Phase 4 counted that as success. Now:

1. Text comes from poppler (``pdf_poppler.extract_pdf_pages``) when
   ``pdftotext`` is installed (``sudo apt install -y poppler-utils``).
2. pdfplumber still gives the page count, scanned-page detection (images,
   char count) and table cells, but its tables are kept only if their text
   passes the quality check.
3. The extracted text is checked (``assess_text_quality``). Garbled text
   raises ``GarbledTextError`` instead of being ingested; fragmented text is
   kept with a warning.
4. Without ``pdftotext`` the adapter falls back to pdfplumber and says so;
   Persian PDFs then usually fail as garbled, with the install hint.
"""

from __future__ import annotations

from pathlib import Path

from dataclasses import dataclass, field

from rag_core.ingestion.domain.errors import POPPLER_INSTALL, GarbledTextError, ParseFailedError
from rag_core.ingestion.domain.model import BlockKind, ContentBlock
from rag_core.ingestion.domain.text_quality import TextQuality, assess_text_quality
from rag_core.ingestion.infrastructure import pdf_poppler

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


@dataclass(frozen=True)
class PdfParseResult:
    blocks: list[ContentBlock]
    scanned_pages: tuple[int, ...]
    page_count: int
    engine: str
    quality: TextQuality
    warnings: tuple[str, ...] = ()
    info: dict[str, object] = field(default_factory=dict)


def _paragraph_blocks(pages: list[tuple[int, list[str]]]) -> list[ContentBlock]:
    blocks: list[ContentBlock] = []
    for number, paragraphs in pages:
        for paragraph in paragraphs:
            text = paragraph.strip()
            if not text:
                continue
            blocks.append(
                ContentBlock(
                    kind=BlockKind.PARAGRAPH,
                    text=text,
                    index=len(blocks),
                    page=number,
                    paragraph_index=len(blocks),
                )
            )
    return blocks


def _append_tables(blocks: list[ContentBlock], number: int, tables: list[ContentBlock], page_text: str) -> None:
    for table_block in tables:
        if not table_block.text or table_block.text in page_text:
            continue
        if assess_text_quality(table_block.text).is_garbled:
            continue  # poppler text already holds the cell text in readable form
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


def parse_pdf_detailed(path: Path, *, pdftotext: str | None | bool = True) -> PdfParseResult:
    """Parse a PDF. ``pdftotext=False`` forces the pdfplumber fallback (tests)."""
    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover
        raise ParseFailedError(str(path), "pdfplumber is not installed") from exc

    exe: str | None
    if pdftotext is False:
        exe = None
    elif isinstance(pdftotext, str):
        exe = pdftotext
    else:
        exe = pdf_poppler.find_pdftotext()

    warnings: list[str] = []
    info: dict[str, object] = {}
    poppler_pages: dict[int, list[str]] = {}
    engine = "pdfplumber"
    if exe is not None:
        try:
            pages, info = pdf_poppler.extract_pdf_pages(path, exe)
            poppler_pages = {p.number: list(p.paragraphs) for p in pages}
            engine = "pdftotext"
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"pdftotext failed ({exc}); fell back to pdfplumber")
    else:
        warnings.append(f"pdftotext not found; using pdfplumber fallback. Install it with: {POPPLER_INSTALL}")

    scanned: list[int] = []
    page_texts: list[tuple[int, list[str]]] = []
    tables_by_page: dict[int, list[ContentBlock]] = {}
    try:
        with pdfplumber.open(path) as pdf:
            page_count = len(pdf.pages)
            for number, page in enumerate(pdf.pages, start=1):
                if engine == "pdftotext":
                    paragraphs = poppler_pages.get(number, [])
                    text = "\n\n".join(paragraphs)
                else:
                    try:
                        raw = page.extract_text() or ""
                    except Exception as exc:  # noqa: BLE001
                        raise ParseFailedError(str(path), f"page {number}: {exc}") from exc
                    text = raw.strip()
                    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
                if _page_is_scanned(page, text):
                    scanned.append(number)
                page_texts.append((number, paragraphs))
                tables_by_page[number] = _tables_as_blocks(page, number, 0)
    except ParseFailedError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ParseFailedError(str(path), str(exc)) from exc

    blocks: list[ContentBlock] = []
    for number, paragraphs in page_texts:
        page_blocks = _paragraph_blocks([(number, paragraphs)])
        for block in page_blocks:
            blocks.append(
                ContentBlock(
                    kind=block.kind,
                    text=block.text,
                    index=len(blocks),
                    page=number,
                    paragraph_index=len(blocks),
                )
            )
        _append_tables(blocks, number, tables_by_page.get(number, []), "\n\n".join(paragraphs))

    full_text = "\n\n".join(b.text for b in blocks)
    quality = assess_text_quality(full_text)
    if quality.is_garbled:
        hint = "" if engine == "pdftotext" else f"Install poppler for correct Persian text: {POPPLER_INSTALL}"
        raise GarbledTextError(str(path), quality.reasons, engine, hint)
    if quality.verdict == "fragmented":
        warnings.append("fragmented PDF text: " + "; ".join(quality.reasons))
    return PdfParseResult(blocks, tuple(scanned), page_count, engine, quality, tuple(warnings), info)


def parse_pdf(path: Path) -> tuple[list[ContentBlock], tuple[int, ...], int]:
    """Backward-compatible wrapper: (blocks, scanned_page_numbers, page_count). Never runs OCR."""
    result = parse_pdf_detailed(path)
    return result.blocks, result.scanned_pages, result.page_count
