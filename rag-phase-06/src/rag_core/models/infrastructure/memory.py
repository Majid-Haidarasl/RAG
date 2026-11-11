from __future__ import annotations

from rag_core.models.domain.model import PHASE2_BASELINE, ModelRegistryEntry, PromptTemplate
from rag_core.shared_kernel.errors import NotFoundError


class InMemoryModelRegistry:
    def __init__(self, entries: list[ModelRegistryEntry] | None = None) -> None:
        items = entries if entries is not None else list(PHASE2_BASELINE)
        self._items = {e.model_id: e for e in items}

    def get(self, model_id: str) -> ModelRegistryEntry:
        try:
            return self._items[model_id]
        except KeyError as exc:
            raise NotFoundError(model_id) from exc

    def list_baseline(self) -> list[ModelRegistryEntry]:
        return list(self._items.values())


class InMemoryPromptRegistry:
    def __init__(self) -> None:
        self._items: dict[str, PromptTemplate] = {}

    def get(self, prompt_id: str) -> PromptTemplate:
        try:
            return self._items[prompt_id]
        except KeyError as exc:
            raise NotFoundError(prompt_id) from exc

    def save(self, template: PromptTemplate) -> None:
        self._items[template.prompt_id] = template
