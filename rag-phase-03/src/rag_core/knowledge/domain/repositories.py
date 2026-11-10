from __future__ import annotations

from typing import Protocol

from rag_core.knowledge.domain.model import KnowledgeItem
from rag_core.shared_kernel.identifiers import DocumentId, KnowledgeItemId


class KnowledgeItemRepository(Protocol):
    def get(self, item_id: KnowledgeItemId) -> KnowledgeItem: ...
    def find_by_document(self, document_id: DocumentId) -> KnowledgeItem | None: ...
    def save(self, item: KnowledgeItem) -> None: ...
