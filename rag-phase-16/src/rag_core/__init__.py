"""Offline hierarchical RAG core (ArmanRayan).

Bounded contexts plus a shared kernel (Phase 3), document ingestion
(Phase 4), knowledge lifecycle and dedup (Phase 5), the organizational
hierarchy registry (Phase 6), issue / sub-issue modeling (Phase 7), the
retrieval core and node-scoped Q&A (Phase 8), executor analysis with the
Issue-Knowledge-Executor model (Phase 9), the LLM-as-judge quality
control (Phase 10), cyclic node processing with upward knowledge transfer
packages (Phase 11) and project, research and gap tracking with key-issue
prioritization (Phase 12), RFP generation from key issues and knowledge
with proposal registry, weighted evaluation and feedback (Phase 13), and
prompt testing with a bilingual gold set, retrieval / prompt / judge
variants and documented tuning choices (Phase 14), and unit-test
completion with a coverage report, hardening tests, a fact pre-check for
the strict judge, an invented-id guard and the release checklist (Phase 15),
and the release check with documentation, presentation and training
material (Phase 16). Domain code never calls Ollama directly.
"""

__version__ = "1.0.0"
