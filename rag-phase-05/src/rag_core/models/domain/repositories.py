from __future__ import annotations

from typing import Protocol

from rag_core.models.domain.model import ModelRegistryEntry, PromptTemplate


class ModelRegistryPort(Protocol):
    def get(self, model_id: str) -> ModelRegistryEntry: ...
    def list_baseline(self) -> list[ModelRegistryEntry]: ...


class PromptRegistry(Protocol):
    def get(self, prompt_id: str) -> PromptTemplate: ...
    def save(self, template: PromptTemplate) -> None: ...
