from __future__ import annotations

from rag_core.knowledge.domain.model import KnowledgeItem
from rag_core.shared_kernel.errors import NotFoundError
from rag_core.shared_kernel.identifiers import DocumentId, KnowledgeItemId


class InMemoryKnowledgeItemRepository:
    def __init__(self) -> None:
        self._items: dict[str, KnowledgeItem] = {}

    def get(self, item_id: KnowledgeItemId) -> KnowledgeItem:
        item = self._items.get(item_id.value)
        if item is None:
            raise NotFoundError(str(item_id))
        return item

    def find_by_document(self, document_id: DocumentId) -> KnowledgeItem | None:
        for item in self._items.values():
            if item.document_id == document_id:
                return item
        return None

    def save(self, item: KnowledgeItem) -> None:
        self._items[item.item_id.value] = item

    def all(self) -> list[KnowledgeItem]:
        return list(self._items.values())

