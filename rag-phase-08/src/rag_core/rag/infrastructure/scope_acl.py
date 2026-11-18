"""Anti-corruption layer: Phase 6 hierarchy → ``ScopePort``.

The only module of the ``rag`` context that imports ``hierarchy``.
"""

from __future__ import annotations

from rag_core.hierarchy.domain.model import Organization
from rag_core.hierarchy.domain.ownership import DocumentOwnership
from rag_core.hierarchy.domain.scope import ScopeResolver, route_question
from rag_core.rag.domain.ports import EscalationRoute
from rag_core.shared_kernel.confidentiality import Confidentiality
from rag_core.shared_kernel.identifiers import DocumentId, NodeIdentifier


class HierarchyScope:
    def __init__(
        self,
        organization: Organization,
        ownership: DocumentOwnership,
        confidentiality_of: dict[str, Confidentiality],
    ) -> None:
        self.org = organization
        self.ownership = ownership
        self.confidentiality_of = confidentiality_of
        self._resolver = ScopeResolver(organization)
        self._cache: dict[str, frozenset[str]] = {}

    def exists(self, node: str) -> bool:
        try:
            return NodeIdentifier(node) in self.org and self.org.get(NodeIdentifier(node)).is_active
        except Exception:  # noqa: BLE001 - invalid id format means "does not exist"
            return False

    def layer_of(self, node: str) -> int | None:
        try:
            return int(self.org.get(NodeIdentifier(node)).layer.value)
        except Exception:  # noqa: BLE001
            return None

    def visible_documents(self, node: str) -> frozenset[str]:
        if node not in self._cache:
            docs = self._resolver.visible_documents(NodeIdentifier(node), self.ownership, self.confidentiality_of)
            self._cache[node] = frozenset(str(d) for d in docs)
        return self._cache[node]

    def owner_of(self, document_id: str) -> str | None:
        owner = self.ownership.owner_of(DocumentId(document_id))
        return None if owner is None else str(owner)

    def route(self, asking: str, evidence_owners: list[str]) -> EscalationRoute:
        decision = route_question(self.org, NodeIdentifier(asking), [NodeIdentifier(o) for o in evidence_owners])
        return EscalationRoute(decision.action.value, str(decision.target), decision.reason)
