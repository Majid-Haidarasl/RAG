"""Deterministic model doubles (Phase 1 unit-test policy, section 5)."""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from rag_core.judging.domain.model import JudgeRubric
from rag_core.models.domain.ports import LlmResult, LvmResult


class FakeEmbeddingModel:
    def __init__(self, dimension: int = 8) -> None:
        self.dimension = dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            digest = sha256(text.encode("utf-8")).digest()
            raw = list(digest[: self.dimension])
            # L2-normalise so cosine == dot product, like bge-m3 via Ollama.
            norm = sum(x * x for x in raw) ** 0.5 or 1.0
            vectors.append([x / norm for x in raw])
        return vectors


class FakeLlm:
    def __init__(self, responses: dict[str, str] | None = None) -> None:
        self.responses = responses or {}
        self.received: list[tuple[str, str, dict[str, str]]] = []

    def complete(
        self,
        prompt_id: str,
        version: str,
        variables: dict[str, str],
        schema: dict[str, Any] | None = None,
        think: bool = False,
    ) -> LlmResult:
        self.received.append((prompt_id, version, dict(variables)))
        key = f"{prompt_id}@{version}"
        text = self.responses.get(key, self.responses.get(prompt_id, "OK"))
        return LlmResult(text=text, think_used=think)


class FakeLvm:
    def read(self, image: bytes, task_prompt: str) -> LvmResult:
        return LvmResult(text="FAKE_LAYOUT")


class FakeJudge:
    def __init__(self, score: int = 18) -> None:
        self.score = score

    def evaluate(self, subject: str, source: str, rubric: JudgeRubric) -> str:
        return f'{{"score": {self.score}, "out_of": 20}}'
