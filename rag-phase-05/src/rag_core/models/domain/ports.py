"""Ports for local models. Adapters must target localhost only (Phase 2 contract)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class LlmResult:
    text: str
    parsed: dict[str, Any] | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    think_used: bool = False


@dataclass(frozen=True)
class LvmResult:
    text: str
    prompt_tokens: int = 0


class EmbeddingPort(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class LlmPort(Protocol):
    def complete(
        self,
        prompt_id: str,
        version: str,
        variables: dict[str, str],
        schema: dict[str, Any] | None = None,
        think: bool = False,
    ) -> LlmResult: ...


class LvmPort(Protocol):
    def read(self, image: bytes, task_prompt: str) -> LvmResult: ...
