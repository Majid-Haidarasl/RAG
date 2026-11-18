"""Offline hierarchical RAG core (ArmanRayan).

Ten bounded contexts plus a shared kernel (Phase 3), document ingestion
(Phase 4), knowledge lifecycle and dedup (Phase 5), the organizational
hierarchy registry (Phase 6) and issue / sub-issue modeling (Phase 7).
Domain code never calls Ollama directly.
"""

__version__ = "0.7.0"
