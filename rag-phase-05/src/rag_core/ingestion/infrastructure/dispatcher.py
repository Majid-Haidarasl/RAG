"""Format router that implements ``DocumentParserPort``."""

from __future__ import annotations

from pathlib import Path

from dataclasses import dataclass

from rag_core.ingestion.domain.errors import ParseFailedError, UnsupportedFormatError
from rag_core.ingestion.domain.model import ContentBlock, FileFormat
from rag_core.ingestion.infrastructure.parser_doc import parse_doc
from rag_core.ingestion.infrastructure.parser_docx import parse_docx
from rag_core.ingestion.infrastructure.parser_pdf import parse_pdf
from rag_core.knowledge.domain.ports import DocumentParserPort, ParsedDocument
from rag_core.shared_kernel.language import LanguageCode


@dataclass(frozen=True)
class ParsedWithBlocks(ParsedDocument):
    """ParsedDocument plus the ordered blocks used by the Phase 4 pipeline."""

    blocks: tuple[ContentBlock, ...] = ()
    file_format: FileFormat = FileFormat.DOCX
    is_scanned: bool = False
    scanned_pages: tuple[int, ...] = ()
    converted_from: str | None = None


def _join_text(blocks: list[ContentBlock]) -> str:
    parts = [b.text.strip() for b in blocks if b.text.strip()]
    return "\n\n".join(parts)


def _headings(blocks: list[ContentBlock]) -> tuple[str, ...]:
    return tuple(b.text for b in blocks if b.kind.value == "heading" and b.text)


class CompositeDocumentParser:
    """Parse a local DOC, DOCX or PDF file. Does not open a network socket."""

    def parse(self, path: Path) -> ParsedWithBlocks:
        path = Path(path)
        if not path.is_file():
            raise ParseFailedError(str(path), "file not found")
        suffix = path.suffix.lower()
        converted_from: str | None = None
        scanned: tuple[int, ...] = ()
        page_count = 0
        file_format: FileFormat

        if suffix == ".docx":
            file_format = FileFormat.DOCX
            blocks = parse_docx(path)
        elif suffix == ".doc":
            file_format = FileFormat.DOC
            blocks, converted = parse_doc(path)
            converted_from = str(converted)
        elif suffix == ".pdf":
            file_format = FileFormat.PDF
            blocks, scanned, page_count = parse_pdf(path)
        else:
            raise UnsupportedFormatError(suffix or path.name)

        if file_format != FileFormat.PDF:
            # python-docx has no reliable page count without rendering.
            page_count = 0

        return ParsedWithBlocks(
            text=_join_text(blocks),
            headings=_headings(blocks),
            language=None,
            page_count=page_count,
            blocks=tuple(blocks),
            file_format=file_format,
            is_scanned=bool(scanned),
            scanned_pages=scanned,
            converted_from=converted_from,
        )


# Structural check that the class matches the Phase 3 port.
def _port_ok(parser: DocumentParserPort) -> DocumentParserPort:
    return parser


_ = _port_ok
