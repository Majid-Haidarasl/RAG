"""Use-case services for registering layers and nodes (UC-01)."""

from __future__ import annotations

from rag_core.hierarchy.domain.model import Layer, Node, Organization
from rag_core.hierarchy.domain.repositories import OrganizationRepository


class RegisterHierarchyService:
    def __init__(self, repository: OrganizationRepository) -> None:
        self._repo = repository

    def register_layer(self, layer: Layer) -> None:
        org = self._repo.get()
        org.register_layer(layer)
        self._repo.save(org)

    def register_node(self, node: Node) -> None:
        org = self._repo.get()
        org.register_node(node)
        self._repo.save(org)

    def current(self) -> Organization:
        return self._repo.get()
