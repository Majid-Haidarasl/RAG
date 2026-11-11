"""Value objects for parsed blocks, source anchors and produced chunks."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from rag_core.shared_kernel.language import LanguageCode


class BlockKind(StrEnum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    TABLE = "table"
    TABLE_CELL = "table_cell"
    PAGE_BREAK = "page_break"


class FileFormat(StrEnum):
    DOCX = "docx"
    DOC = "doc"
    PDF = "pdf"


@dataclass(frozen=True)
class SourceAnchor:
    """Pointer used later by citations (Phase 8).

    DOCX files usually have no reliable printed page number, so ``page`` is
    then omitted. Character offsets are measured on the *normalized* block
    text, which is what the chunker and the index will store.
    """

    document_id: str
    block_index: int
    char_start: int
    char_end: int
    page: int | None = None
    paragraph_index: int | None = None
    table_index: int | None = None
    row: int | None = None
    column: int | None = None
    heading_path: str = ""

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "document_id": self.document_id,
            "block_index": self.block_index,
            "char_start": self.char_start,
            "char_end": self.char_end,
        }
        if self.page is not None:
            data["page"] = self.page
        if self.paragraph_index is not None:
            data["paragraph_index"] = self.paragraph_index
        if self.table_index is not None:
            data["table_index"] = self.table_index
            data["row"] = self.row
            data["column"] = self.column
        if self.heading_path:
            data["heading_path"] = self.heading_path
        return data


@dataclass(frozen=True)
class ContentBlock:
    kind: BlockKind
    text: str
    index: int
    heading_path: str = ""
    heading_level: int | None = None
    page: int | None = None
    paragraph_index: int | None = None
    table_index: int | None = None
    row: int | None = None
    column: int | None = None
    cells: tuple[tuple[str, ...], ...] = ()

    def anchor(self, document_id: str, start: int = 0, end: int | None = None) -> SourceAnchor:
        return SourceAnchor(
            document_id=document_id,
            block_index=self.index,
            char_start=start,
            char_end=len(self.text) if end is None else end,
            page=self.page,
            paragraph_index=self.paragraph_index,
            table_index=self.table_index,
            row=self.row,
            column=self.column,
            heading_path=self.heading_path,
        )


@dataclass(frozen=True)
class TextChunk:
    chunk_id: str
    order: int
    text: str
    heading_path: str
    anchors: tuple[SourceAnchor, ...]
    kind: str = "prose"

    def to_dict(self) -> dict[str, object]:
        return {
            "chunk_id": self.chunk_id,
            "order": self.order,
            "text": self.text,
            "heading_path": self.heading_path,
            "kind": self.kind,
            "anchors": [a.to_dict() for a in self.anchors],
            "char_count": len(self.text),
        }


@dataclass
class NormalizationReport:
    yeh_kaf: int = 0
    zwnj: int = 0
    id_digits: int = 0
    arabic_indic: int = 0
    replacements: list[tuple[str, str]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.yeh_kaf + self.zwnj + self.id_digits + self.arabic_indic

    def to_dict(self) -> dict[str, object]:
        return {
            "yeh_kaf": self.yeh_kaf,
            "zwnj": self.zwnj,
            "id_digits": self.id_digits,
            "arabic_indic": self.arabic_indic,
            "total": self.total,
            "id_replacements": [{"from": a, "to": b} for a, b in self.replacements],
        }


@dataclass
class IngestedDocument:
    path: Path
    file_format: FileFormat
    document_id: str
    language: LanguageCode | None
    text: str
    blocks: tuple[ContentBlock, ...]
    headings: tuple[str, ...]
    page_count: int
    file_sha256: str
    byte_size: int
    is_scanned: bool = False
    scanned_pages: tuple[int, ...] = ()
    normalization: NormalizationReport = field(default_factory=NormalizationReport)
    metadata: dict[str, object] = field(default_factory=dict)
    chunks: tuple[TextChunk, ...] = ()
    warnings: list[str] = field(default_factory=list)
    converted_from: str | None = None

    def to_summary(self) -> dict[str, object]:
        return {
            "path": str(self.path),
            "format": self.file_format.value,
            "document_id": self.document_id,
            "language": None if self.language is None else self.language.value,
            "page_count": self.page_count,
            "block_count": len(self.blocks),
            "chunk_count": len(self.chunks),
            "char_count": len(self.text),
            "is_scanned": self.is_scanned,
            "scanned_pages": list(self.scanned_pages),
            "file_sha256": self.file_sha256,
            "normalization": self.normalization.to_dict(),
            "warnings": list(self.warnings),
            "converted_from": self.converted_from,
        }
