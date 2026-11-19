"""Offline hierarchical RAG core (ArmanRayan).

Ten bounded contexts plus a shared kernel (Phase 3), document ingestion
(Phase 4), knowledge lifecycle and dedup (Phase 5), the organizational
hierarchy registry (Phase 6), issue / sub-issue modeling (Phase 7), the
retrieval core and node-scoped Q&A (Phase 8), executor analysis with the
Issue-Knowledge-Executor model (Phase 9), the LLM-as-judge quality
control (Phase 10) and cyclic node processing with upward knowledge transfer
packages (Phase 11).
Domain code never calls Ollama directly.
"""

__version__ = "0.11.0"
