"""RAG application services (Phase 8). Indexing lives in ``indexing.py``."""

from rag_core.rag.application.indexing import IndexBuilder, build_retriever, records_from_lifecycle

__all__ = ["IndexBuilder", "build_retriever", "records_from_lifecycle"]
