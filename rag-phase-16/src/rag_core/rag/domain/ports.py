"""Outbound ports of the RAG core. Adapters live in ``rag.infrastructure``.

The embedding port is the Phase 3 ``EmbeddingPort`` (models context), reused
here rather than redefined.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from rag_core.models.domain.ports import EmbeddingPort
from rag_core.rag.domain.records import ChunkRecord

__all__ = [
    "ChunkStorePort",
    "EmbeddingPort",
    "EscalationRoute",
    "ScopePort",
    "VectorIndexPort",
]


class ChunkStorePort(Protocol):
    def get(self, key: str) -> ChunkRecord: ...
    def all(self) -> list[ChunkRecord]: ...
    def __len__(self) -> int: ...


class VectorIndexPort(Protocol):
    """Dense index. Scores are cosine similarities in [-1, 1]."""

    def upsert(self, key: str, vector: list[float]) -> None: ...
    def remove(self, key: str) -> None: ...
    def keys(self) -> set[str]: ...
    def search(
        self, vector: list[float], k: int, allowed: Iterable[str] | None = None
    ) -> list[tuple[str, float]]: ...


@dataclass(frozen=True)
class EscalationRoute:
    action: str  # "answer" | "escalate"
    target: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"action": self.action, "target": self.target, "reason": self.reason}


class ScopePort(Protocol):
    """Phase 6 hierarchy seen from retrieval (anti-corruption layer)."""

    def exists(self, node: str) -> bool: ...
    def visible_documents(self, node: str) -> frozenset[str]: ...
    def owner_of(self, document_id: str) -> str | None: ...
    def route(self, asking: str, evidence_owners: list[str]) -> EscalationRoute: ...
