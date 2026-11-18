"""DOCX adapter: walks body blocks in document order, including tables."""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from rag_core.ingestion.domain.errors import ParseFailedError
from rag_core.ingestion.domain.model import BlockKind, ContentBlock


def iter_block_items(document: Document):
    """Yield paragraphs and tables in the order they appear in ``w:body``."""
    body = document.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, document)
        elif child.tag == qn("w:tbl"):
            yield Table(child, document)


def _heading_level(paragraph: Paragraph) -> int | None:
    style = paragraph.style
    if style is not None and style.name:
        name = style.name.strip()
        lower = name.lower()
        if lower.startswith("heading"):
            tail = lower.replace("heading", "").strip()
            if tail.isdigit():
                return int(tail)
        # Some Persian templates use "عنوان 1"
        if name.startswith("عنوان"):
            tail = name.replace("عنوان", "").strip()
            if tail.isdigit():
                return int(tail)
    pPr = paragraph._p.find(qn("w:pPr"))
    if pPr is not None:
        outline = pPr.find(qn("w:outlineLvl"))
        if outline is not None:
            value = outline.get(qn("w:val"))
            if value is not None and value.isdigit():
                return int(value) + 1
    return None


def _is_list_item(paragraph: Paragraph) -> bool:
    pPr = paragraph._p.find(qn("w:pPr"))
    if pPr is None:
        return False
    return pPr.find(qn("w:numPr")) is not None


def _table_rows(table: Table) -> tuple[tuple[str, ...], ...]:
    rows: list[tuple[str, ...]] = []
    for row in table.rows:
        cells = tuple((cell.text or "").strip() for cell in row.cells)
        rows.append(cells)
    return tuple(rows)


def _format_table(rows: tuple[tuple[str, ...], ...]) -> str:
    lines: list[str] = []
    for row in rows:
        lines.append(" | ".join(row))
    return "\n".join(lines)


def parse_docx(path: Path) -> list[ContentBlock]:
    try:
        document = Document(path)
    except Exception as exc:  # noqa: BLE001 — surface any parse failure clearly
        raise ParseFailedError(str(path), str(exc)) from exc

    blocks: list[ContentBlock] = []
    heading_stack: list[tuple[int, str]] = []
    paragraph_index = 0
    table_index = 0

    def heading_path() -> str:
        return " > ".join(title for _, title in heading_stack)

    for item in iter_block_items(document):
        if isinstance(item, Paragraph):
            text = (item.text or "").strip()
            level = _heading_level(item)
            if level is not None and text:
                heading_stack = [(lvl, title) for lvl, title in heading_stack if lvl < level]
                heading_stack.append((level, text))
                blocks.append(
                    ContentBlock(
                        kind=BlockKind.HEADING,
                        text=text,
                        index=len(blocks),
                        heading_path=heading_path(),
                        heading_level=level,
                        paragraph_index=paragraph_index,
                    )
                )
                paragraph_index += 1
                continue
            if not text:
                paragraph_index += 1
                continue
            kind = BlockKind.LIST_ITEM if _is_list_item(item) else BlockKind.PARAGRAPH
            blocks.append(
                ContentBlock(
                    kind=kind,
                    text=text,
                    index=len(blocks),
                    heading_path=heading_path(),
                    paragraph_index=paragraph_index,
                )
            )
            paragraph_index += 1
            continue

        if isinstance(item, Table):
            rows = _table_rows(item)
            text = _format_table(rows)
            if text.strip():
                blocks.append(
                    ContentBlock(
                        kind=BlockKind.TABLE,
                        text=text,
                        index=len(blocks),
                        heading_path=heading_path(),
                        table_index=table_index,
                        cells=rows,
                    )
                )
            table_index += 1

    return blocks
