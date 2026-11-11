from __future__ import annotations

from typing import Protocol

from rag_core.hierarchy.domain.model import Organization
from rag_core.shared_kernel.identifiers import NodeIdentifier


class OrganizationRepository(Protocol):
    def get(self) -> Organization: ...
    def save(self, organization: Organization) -> None: ...
    def exists(self, node_id: NodeIdentifier) -> bool: ...


class LayerRegistryRepository(Protocol):
    def get(self) -> Organization: ...
    def save(self, organization: Organization) -> None: ...
