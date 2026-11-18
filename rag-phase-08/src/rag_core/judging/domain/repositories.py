from __future__ import annotations

from typing import Protocol

from rag_core.judging.domain.model import JudgeEvaluation


class JudgeEvaluationRepository(Protocol):
    def save(self, evaluation: JudgeEvaluation) -> None: ...
