from __future__ import annotations

from typing import Protocol

from rag_core.rag.domain.model import RetrievalSession


class RetrievalSessionRepository(Protocol):
    def save(self, session: RetrievalSession) -> None: ...
