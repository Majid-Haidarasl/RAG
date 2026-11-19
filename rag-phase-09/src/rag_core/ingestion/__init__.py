"""Document ingestion bounded capability (Phase 4).

Parsers implement ``DocumentParserPort`` from Knowledge Management.
Chunking and metadata live in this package so later phases can index chunks
without changing the domain aggregates of Phase 3.
"""

from rag_core.ingestion.application.pipeline import ingest_file, ingest_paths
from rag_core.ingestion.infrastructure.dispatcher import CompositeDocumentParser

__all__ = ["CompositeDocumentParser", "ingest_file", "ingest_paths"]
