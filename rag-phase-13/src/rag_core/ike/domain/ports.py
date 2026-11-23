"""Ports of the IKE context.

* ``KnowledgeSearchPort``: node-scoped knowledge search (the Phase 8
  retriever behind ``ike.infrastructure.retrieval_acl``);
* ``SummaryChatPort``: local chat model for summary text (qwen3:8b via
  Ollama in production, a fake in tests);
* the shared-kernel ``FactValidator`` checks generated summaries.
"""

from __future__ import annotations

from typing import Protocol

from rag_core.ike.domain.comparison import KnowledgeSearchResult
from rag_core.models.domain.ports import LlmResult
from rag_core.shared_kernel.fact_ports import FactValidator

__all__ = ["FactValidator", "KnowledgeSearchPort", "SummaryChatPort"]


class KnowledgeSearchPort(Protocol):
    def search(self, query: str, node: str, top_k: int) -> KnowledgeSearchResult: ...


class SummaryChatPort(Protocol):
    def generate(self, system: str, user: str) -> LlmResult: ...
