"""Offline hierarchical RAG core (ArmanRayan).

Ten bounded contexts plus a shared kernel (Phase 3) and a document
ingestion pipeline (Phase 4). Domain code never calls Ollama directly.
"""

__version__ = "0.4.0"
