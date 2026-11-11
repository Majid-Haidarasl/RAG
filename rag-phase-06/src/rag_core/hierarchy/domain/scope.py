"""Retrieval scope resolution and leaf-node boundary / escalation rules.

Scope rules (which nodes' knowledge a query at node X may see):

S1  X's own knowledge and the knowledge of every active descendant (chain of
    command: a parent may read what its units hold).
S2  Ancestors' knowledge flows down as policy, but restricted ancestor items
    stay hidden unless X is an owner/co-owner (e.g. AR-BRD-003 is not visible
    to a web team).
S3  The L4 knowledge repository (N-LIB) serves every L0–L3 node; its items
    keep their own confidentiality.
S4  Siblings and cousins are not visible, unless X is a co-owner of the item.
S5  Restricted items are visible only to their owner, co-owners, nodes the
    document explicitly describes or governs (``described_in`` readers, e.g.
    N-CEO for AR-BRD-003) and the ancestors (chain of command) of the owner
    or a co-owner.
S6  A retired node cannot be a query scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from rag_core.hierarchy.domain.model import NodeType, Organization
from rag_core.hierarchy.domain.ownership import DocumentOwnership
from rag_core.shared_kernel.confidentiality import Confidentiality
from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.identifiers import DocumentId, NodeIdentifier


@dataclass(frozen=True)
class RetrievalScope:
    node: NodeIdentifier
    own_and_descendants: frozenset[NodeIdentifier]
    ancestors: frozenset[NodeIdentifier]
    repositories: frozenset[NodeIdentifier]
    chain_of_command_of: dict[NodeIdentifier, frozenset[NodeIdentifier]]

    @property
    def visible_nodes(self) -> frozenset[NodeIdentifier]:
        return self.own_and_descendants | self.ancestors | self.repositories

    def can_see(
        self,
        owner: NodeIdentifier,
        confidentiality: Confidentiality,
        co_owners: tuple[NodeIdentifier, ...] = (),
        readers: tuple[NodeIdentifier, ...] = (),
    ) -> bool:
        if confidentiality is Confidentiality.PUBLIC:
            return True
        holders = (owner, *co_owners)
        if self.node in holders or self.node in readers:
            return True
        if confidentiality is Confidentiality.RESTRICTED:
            # S5: owner, co-owners and their chain of command only.
            return any(self.node in self.chain_of_command_of.get(h, frozenset()) for h in holders)
        # internal / per_item (document-level value decides; treated as internal here)
        if owner in self.own_and_descendants or owner in self.repositories or owner in self.ancestors:
            return True
        return any(c in self.own_and_descendants for c in co_owners)


class ScopeResolver:
    def __init__(self, organization: Organization) -> None:
        self.org = organization

    def resolve(self, node_id: NodeIdentifier) -> RetrievalScope:
        node = self.org.get(node_id)
        if not node.is_active:
            raise InvariantError(f"retired node {node_id} cannot be a retrieval scope")
        own = frozenset({node_id, *(d.identifier for d in self.org.descendants(node_id, active_only=True))})
        ancestors = frozenset(a.identifier for a in self.org.ancestors(node_id))
        repos = frozenset(
            n.identifier
            for n in self.org.active_nodes()
            if n.node_type == NodeType.KNOWLEDGE_REPOSITORY and n.identifier != node_id
        )
        if node.node_type == NodeType.KNOWLEDGE_REPOSITORY:
            repos = frozenset()
        chain = {n.identifier: frozenset(a.identifier for a in self.org.ancestors(n.identifier)) for n in self.org.active_nodes()}
        return RetrievalScope(node_id, own, ancestors, repos, chain)

    def visible_documents(
        self,
        node_id: NodeIdentifier,
        ownership: DocumentOwnership,
        confidentiality_of: dict[str, Confidentiality],
    ) -> list[DocumentId]:
        scope = self.resolve(node_id)
        out: list[DocumentId] = []
        for doc in ownership.documents():
            owner = ownership.owner_of(doc)
            if owner is None:
                continue
            conf = confidentiality_of.get(str(doc), Confidentiality.INTERNAL)
            if scope.can_see(owner, conf, ownership.co_owners_of(doc), ownership.readers_of(doc)):
                out.append(doc)
        return out


class RoutingAction(StrEnum):
    ANSWER = "answer"
    ESCALATE = "escalate"


@dataclass(frozen=True)
class RoutingDecision:
    action: RoutingAction
    target: NodeIdentifier
    reason: str


@dataclass(frozen=True)
class LeafBoundary:
    """What a leaf node owns and may answer, and where it escalates."""

    node: NodeIdentifier
    owned_documents: tuple[DocumentId, ...]
    co_owned_documents: tuple[DocumentId, ...]
    activity_domain: str
    escalation_target: NodeIdentifier | None


def leaf_boundary(org: Organization, node_id: NodeIdentifier, ownership: DocumentOwnership) -> LeafBoundary:
    from rag_core.hierarchy.domain.ownership import OwnershipRole

    node = org.get(node_id)
    if org.active_children_of(node_id):
        raise InvariantError(f"{node_id} is not a leaf")
    return LeafBoundary(
        node_id,
        tuple(ownership.documents_of(node_id, OwnershipRole.OWNER)),
        tuple(ownership.documents_of(node_id, OwnershipRole.CO_OWNER)),
        node.activity_domain,
        node.escalation_target,
    )


def route_question(
    org: Organization,
    asking: NodeIdentifier,
    evidence_owners: list[NodeIdentifier],
    *,
    reserved_decision: bool = False,
) -> RoutingDecision:
    """Answer at ``asking`` or escalate (AR-ORG-002 s.7, s.4 decision control).

    * Evidence owned inside the asking node's subtree, by an ancestor, or by
      the repository → the node answers.
    * Otherwise escalate to the lowest common ancestor of the asking node and
      the out-of-scope owners: siblings → the deputy; across deputies → CEO.
    * A reserved decision (AR-BRD-003 thresholds) always goes to the root.
    """
    node = org.get(asking)
    if not node.is_active:
        raise InvariantError(f"retired node {asking} cannot route questions")
    if reserved_decision:
        root = org.root().identifier
        return RoutingDecision(RoutingAction.ESCALATE, root, "reserved decision: Board approval required")
    scope = ScopeResolver(org).resolve(asking)
    outside = [o for o in evidence_owners if o not in scope.visible_nodes]
    if not outside:
        return RoutingDecision(RoutingAction.ANSWER, asking, "all evidence is within the node's scope")
    target = org.lowest_common_ancestor(asking, *outside)
    if target == asking:  # cannot happen for out-of-scope owners, kept defensive
        target = node.escalation_target or asking
    return RoutingDecision(
        RoutingAction.ESCALATE,
        target,
        f"evidence owned outside scope by {', '.join(str(o) for o in outside)}",
    )
