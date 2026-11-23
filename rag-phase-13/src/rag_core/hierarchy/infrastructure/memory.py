from __future__ import annotations

from rag_core.hierarchy.domain.model import Organization
from rag_core.shared_kernel.identifiers import NodeIdentifier


class InMemoryOrganizationRepository:
    def __init__(self, organization: Organization | None = None) -> None:
        self._org = organization if organization is not None else Organization()

    def get(self) -> Organization:
        return self._org

    def save(self, organization: Organization) -> None:
        self._org = organization

    def exists(self, node_id: NodeIdentifier) -> bool:
        return node_id in self._org
