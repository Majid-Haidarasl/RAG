"""Inbound parsing and outbound indexing ports. Adapters live in later phases."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from rag_core.shared_kernel.language import LanguageCode


@dataclass(frozen=True)
class ParsedDocument:
    text: str
    headings: tuple[str, ...] = ()
    language: LanguageCode | None = None
    page_count: int = 0


class DocumentParserPort(Protocol):
    """Parse a local DOC, DOCX or PDF file. Must not open a network socket."""

    def parse(self, path: Path) -> ParsedDocument: ...


class VectorStorePort(Protocol):
    """Local vector index. Implementation is deferred (ingestion phases)."""

    def upsert(self, chunk_id: str, vector: list[float], metadata: dict[str, str]) -> None: ...
    def search(self, vector: list[float], k: int, filters: dict[str, str] | None = None) -> list[str]: ...
    def delete(self, chunk_id: str) -> None: ...
