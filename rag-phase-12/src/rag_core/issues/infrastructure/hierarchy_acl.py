"""Anti-corruption layer: Phase 6 hierarchy context → issues ``OrgDirectory`` port.

Only this module imports the hierarchy context. It translates the
``Organization`` aggregate into ``OrgNodeView`` / ``OrgRoute`` values and
reuses the Phase 6 escalation logic (``route_question``).
"""

from __future__ import annotations

from pathlib import Path

from rag_core.hierarchy.application.workflows import load_and_validate
from rag_core.hierarchy.domain.model import Organization
from rag_core.hierarchy.domain.scope import route_question
from rag_core.issues.domain.ports import OrgNodeView, OrgRoute
from rag_core.shared_kernel.errors import InvariantError, NotFoundError
from rag_core.shared_kernel.identifiers import NodeIdentifier


class HierarchyOrgDirectory:
    def __init__(self, organization: Organization) -> None:
        self._org = organization

    @classmethod
    def from_registry(cls, registry_dir: Path) -> HierarchyOrgDirectory:
        loaded = load_and_validate(registry_dir)
        if loaded.organization is None:
            errors = "; ".join(str(e) for e in loaded.report.errors[:5])
            raise InvariantError(f"hierarchy registry is invalid: {errors}")
        return cls(loaded.organization)

    def exists(self, node_id: str) -> bool:
        try:
            return (
                NodeIdentifier(node_id) in self._org
                and self._org.get(NodeIdentifier(node_id)).is_active
            )
        except InvariantError:
            return False

    def node(self, node_id: str) -> OrgNodeView:
        if not self.exists(node_id):
            raise NotFoundError(f"unknown or retired node {node_id}")
        nid = NodeIdentifier(node_id)
        node = self._org.get(nid)
        return OrgNodeView(
            node_id=node_id,
            layer=node.layer.value,
            depth=self._org.depth(nid),
            path=tuple(str(n) for n in self._org.path(nid)),
            is_active=node.is_active,
        )

    def lowest_common_ancestor(self, node_ids: list[str]) -> str:
        for n in node_ids:
            self.node(n)
        return str(
            self._org.lowest_common_ancestor(*(NodeIdentifier(n) for n in node_ids))
        )

    def route(
        self,
        asking: str,
        evidence_owners: list[str],
        *,
        reserved_decision: bool = False,
    ) -> OrgRoute:
        decision = route_question(
            self._org,
            NodeIdentifier(asking),
            [NodeIdentifier(n) for n in evidence_owners],
            reserved_decision=reserved_decision,
        )
        return OrgRoute(decision.action.value, str(decision.target), decision.reason)
