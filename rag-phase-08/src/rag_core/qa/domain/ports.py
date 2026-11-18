from __future__ import annotations

from typing import Protocol

from rag_core.models.domain.ports import LlmResult


class ChatModelPort(Protocol):
    """Local chat model (qwen3:8b via Ollama in production, a fake in tests)."""

    def generate(self, system: str, user: str) -> LlmResult: ...
