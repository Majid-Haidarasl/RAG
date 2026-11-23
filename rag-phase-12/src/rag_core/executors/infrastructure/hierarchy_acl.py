"""Anti-corruption layer: Phase 6 hierarchy → executors ``TeamDirectory`` port.

The only module of the executors context that imports ``hierarchy``.
"""

from __future__ import annotations

from pathlib import Path

from rag_core.executors.domain.ports import TeamView
from rag_core.hierarchy.application.workflows import load_and_validate
from rag_core.hierarchy.domain.model import Organization
from rag_core.shared_kernel.errors import InvariantError, NotFoundError
from rag_core.shared_kernel.identifiers import NodeIdentifier


class HierarchyTeamDirectory:
    def __init__(self, organization: Organization) -> None:
        self._org = organization

    @classmethod
    def from_registry(cls, registry_dir: Path) -> HierarchyTeamDirectory:
        loaded = load_and_validate(registry_dir)
        if loaded.organization is None:
            errors = "; ".join(str(e) for e in loaded.report.errors[:5])
            raise InvariantError(f"hierarchy registry is invalid: {errors}")
        return cls(loaded.organization)

    def exists(self, node_id: str) -> bool:
        try:
            nid = NodeIdentifier(node_id)
        except InvariantError:
            return False
        return nid in self._org and self._org.get(nid).is_active

    def team(self, node_id: str) -> TeamView:
        if not self.exists(node_id):
            raise NotFoundError(f"unknown or retired node {node_id}")
        node = self._org.get(NodeIdentifier(node_id))
        return TeamView(
            node_id=node_id,
            name_en=node.name_en,
            name_fa=node.name_fa,
            layer=int(node.layer.value),
            parent_id=str(node.parent_id) if node.parent_id else None,
            is_active=node.is_active,
        )
