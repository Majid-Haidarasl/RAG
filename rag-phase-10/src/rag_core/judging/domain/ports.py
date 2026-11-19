"""Ports of the judging context."""

from __future__ import annotations

from typing import Protocol

from rag_core.judging.domain.cases import JudgeCase
from rag_core.judging.domain.results import JudgeResult
from rag_core.models.domain.ports import LlmResult


class JudgeModelPort(Protocol):
    """Local chat model used as the judge (qwen3:8b via Ollama, a fake in tests)."""

    def generate(self, system: str, user: str) -> LlmResult: ...


class CaseJudge(Protocol):
    """Anything that turns a ``JudgeCase`` into a ``JudgeResult`` (rule judge, LLM judge)."""

    name: str

    def judge(self, case: JudgeCase) -> JudgeResult: ...
