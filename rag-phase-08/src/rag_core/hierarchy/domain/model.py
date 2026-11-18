"""Hierarchy aggregates: LayerRegistry (as Organization.layers) and Organization.

Phase 6 adds: node status and retirement, move, explicit layer-skip exemptions
(Q3: N-LIB L4 → N-CEO L1), path/ancestor/descendant queries, lowest common
ancestor, and per-layer transfer requirements on ``Layer``.

Naming: issue #6 says "organization"; the bounded context stays ``hierarchy``
and its aggregate root is ``Organization`` (no duplicate package).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from rag_core.shared_kernel.confidentiality import Confidentiality
from rag_core.shared_kernel.errors import InvariantError, NotFoundError
from rag_core.shared_kernel.events import DomainEvent
from rag_core.shared_kernel.identifiers import NodeIdentifier
from rag_core.shared_kernel.layer import LayerIndex
from rag_core.hierarchy.domain.transfer import TransferRequirement

# Technologies are capability tags, never node names (AR-ORG-002 s.6).
FORBIDDEN_CAPABILITY_NAMES = frozenset(
    {
        "django",
        "laravel",
        "node.js",
        "nodejs",
        "react",
        "flutter",
        "react native",
        "c#",
        ".net",
        "c#/.net",
        "csharp",
    }
)


class NodeType(StrEnum):
    BOARD = "board"
    PARENT_ORGANIZATION = "parent_organization"
    DEPUTY = "deputy"
    UNIT = "unit"
    TEAM = "team"
    KNOWLEDGE_REPOSITORY = "knowledge_repository"


_TYPE_LAYERS: dict[NodeType, frozenset[int]] = {
    NodeType.BOARD: frozenset({0}),
    NodeType.PARENT_ORGANIZATION: frozenset({1}),
    NodeType.DEPUTY: frozenset({2}),
    NodeType.UNIT: frozenset({3}),
    NodeType.TEAM: frozenset({3}),
    NodeType.KNOWLEDGE_REPOSITORY: frozenset({4}),
}


class NodeStatus(StrEnum):
    ACTIVE = "active"
    RETIRED = "retired"


DETAIL_LEVELS = ("executive", "managerial", "technical_summary", "detailed_technical")


@dataclass(frozen=True)
class LayerSkipExemption:
    """Allowed non-adjacent parent link, e.g. Q3: knowledge repository L4 under L1."""

    child_type: NodeType
    child_layer: int
    parent_layer: int
    reason: str = ""

    def allows(self, parent: "Node", child: "Node") -> bool:
        return (
            child.node_type == self.child_type
            and child.layer.value == self.child_layer
            and parent.layer.value == self.parent_layer
        )


Q3_LIBRARY_EXEMPTION = LayerSkipExemption(
    NodeType.KNOWLEDGE_REPOSITORY,
    4,
    1,
    "Q3: the L4 knowledge library is a repository, not a reporting layer; it reports to N-CEO (AR-ORG-002 s.8)",
)


@dataclass(frozen=True)
class Layer:
    index: LayerIndex
    code: str
    name_en: str
    name_fa: str
    role: str = ""
    min_judge_score: int | None = 18
    max_package_words: int | None = None
    default_detail_level: str = ""
    knowledge_needed_from_children: str = ""
    required_transfer_format: str = ""
    source_citation_level: str = ""
    default_confidentiality: str = ""
    transfer: TransferRequirement | None = None

    def __post_init__(self) -> None:
        expected = self.index.code
        if self.code != expected:
            raise InvariantError(f"layer code {self.code!r} must equal {expected}")
        if not self.name_en or not self.name_fa:
            raise InvariantError("layer needs bilingual names")
        if self.default_detail_level and self.default_detail_level not in DETAIL_LEVELS:
            raise InvariantError(f"unknown detail level {self.default_detail_level!r}")
        if self.transfer is not None and self.transfer.layer != self.index:
            raise InvariantError("transfer requirement belongs to another layer")


@dataclass
class Node:
    """Entity inside the Organization aggregate. Identity is NodeIdentifier."""

    identifier: NodeIdentifier
    name_en: str
    name_fa: str
    node_type: NodeType
    layer: LayerIndex
    parent_id: NodeIdentifier | None
    is_leaf: bool = False
    activity_domain: str = ""
    cost_center: str = ""
    confidentiality: Confidentiality = Confidentiality.INTERNAL
    capabilities: tuple[str, ...] = ()
    status: NodeStatus = NodeStatus.ACTIVE
    escalation_id: NodeIdentifier | None = None
    head_or_key_contact: str = ""
    transfer_detail_level_to_parent: str = ""
    source_docs: tuple[str, ...] = ()
    successor_id: NodeIdentifier | None = None
    retired_on: date | None = None

    @property
    def is_active(self) -> bool:
        return self.status is NodeStatus.ACTIVE

    @property
    def escalation_target(self) -> NodeIdentifier | None:
        """Where unresolved questions go: explicit escalation node, else the parent."""
        return self.escalation_id or self.parent_id

    def __post_init__(self) -> None:
        if not self.name_en.strip() or not self.name_fa.strip():
            raise InvariantError("node needs bilingual names")
        self._assert_name_is_not_capability(self.name_en)
        self._assert_name_is_not_capability(self.name_fa)
        allowed = _TYPE_LAYERS[self.node_type]
        if self.layer.value not in allowed:
            raise InvariantError(
                f"{self.node_type} cannot sit on {self.layer}"
            )
        if self.parent_id is None and self.node_type != NodeType.BOARD:
            raise InvariantError("only the board node may have no parent")
        if self.parent_id is not None and self.parent_id == self.identifier:
            raise InvariantError("node cannot be its own parent")

    @staticmethod
    def _assert_name_is_not_capability(name: str) -> None:
        key = name.strip().lower()
        if key in FORBIDDEN_CAPABILITY_NAMES:
            raise InvariantError(
                f"capability {name!r} cannot be a node name; store it as a tag"
            )


@dataclass
class Organization:
    """Aggregate root for the node tree. Protects parent–child invariants.

    The tree is small (21 ArmanRayan nodes), so one consistency boundary is
    the right size. Uniqueness, cycles and the adjacent-layer rule are checked
    here, not on a standalone Node aggregate.
    """

    layers: dict[int, Layer] = field(default_factory=dict)
    _nodes: dict[str, Node] = field(default_factory=dict)
    events: list[DomainEvent] = field(default_factory=list)
    exemptions: tuple[LayerSkipExemption, ...] = (Q3_LIBRARY_EXEMPTION,)

    def register_layer(self, layer: Layer) -> None:
        if layer.index.value in self.layers:
            raise InvariantError(f"duplicate layer {layer.index}")
        self.layers[layer.index.value] = layer

    def require_layer(self, index: LayerIndex) -> Layer:
        if index.value not in self.layers:
            raise NotFoundError(f"unknown layer {index}")
        return self.layers[index.value]

    def register_node(self, node: Node) -> None:
        self.require_layer(node.layer)
        if node.identifier.value in self._nodes:
            raise InvariantError(f"duplicate node {node.identifier}")
        if node.parent_id is None:
            roots = [n for n in self._nodes.values() if n.parent_id is None]
            if roots:
                raise InvariantError("exactly one root is allowed")
        else:
            parent = self._require_node(node.parent_id)
            if node.is_active and not parent.is_active:
                raise InvariantError(f"parent {parent.identifier} is retired")
            self._assert_parent_child(parent, node)
        if node.escalation_id is not None and node.escalation_id.value not in self._nodes:
            raise NotFoundError(f"unknown escalation node {node.escalation_id}")
        self._nodes[node.identifier.value] = node
        self.events.append(
            DomainEvent("NodeRegistered", {"node_id": str(node.identifier)})
        )

    def mark_leaf(self, node_id: NodeIdentifier) -> None:
        node = self._require_node(node_id)
        if self.children_of(node_id):
            raise InvariantError(f"cannot mark {node_id} as leaf: it has children")
        node.is_leaf = True
        self.events.append(DomainEvent("NodeMarkedAsLeaf", {"node_id": str(node_id)}))

    # ------------------------------------------------------------ workflows
    def add_node(self, node: Node) -> Node:
        """Add an active node (UC-01 / workflow "add node")."""
        if not node.is_active:
            raise InvariantError("only active nodes can be added")
        self.register_node(node)
        return node

    def move_node(self, node_id: NodeIdentifier, new_parent_id: NodeIdentifier) -> Node:
        """Re-parent a node; its subtree moves with it. Layers never change."""
        node = self._require_active(node_id)
        if node.parent_id is None:
            raise InvariantError("the root cannot be moved")
        new_parent = self._require_active(new_parent_id)
        if new_parent_id == node.parent_id:
            raise InvariantError(f"{node_id} already reports to {new_parent_id}")
        if any(d.identifier == new_parent_id for d in self.descendants(node_id)):
            raise InvariantError("parent–child relation would create a cycle")
        self._assert_parent_child(new_parent, node)
        old = node.parent_id
        node.parent_id = new_parent_id
        if node.escalation_id == old:
            node.escalation_id = None
        self.events.append(
            DomainEvent("NodeMoved", {"node_id": str(node_id), "from": str(old), "to": str(new_parent_id)})
        )
        return node

    def retire_node(
        self,
        node_id: NodeIdentifier,
        successor_id: NodeIdentifier | None = None,
        *,
        on: date | None = None,
        reason: str = "",
    ) -> NodeIdentifier:
        """Retire a node; returns the successor that inherits its knowledge.

        Rules: the root cannot retire; active children must be moved or retired
        first; the successor (default: escalation target / parent) must be an
        active node outside the retiring node's subtree.
        """
        node = self._require_active(node_id)
        if node.parent_id is None:
            raise InvariantError("the root node cannot be retired")
        active_children = [c for c in self.children_of(node_id) if c.is_active]
        if active_children:
            names = ", ".join(str(c.identifier) for c in active_children)
            raise InvariantError(f"{node_id} still has active children ({names}); move or retire them first")
        target_id = successor_id or node.escalation_target
        assert target_id is not None
        if target_id == node_id:
            raise InvariantError("a node cannot succeed itself")
        successor = self._require_active(target_id)
        if node.node_type == NodeType.KNOWLEDGE_REPOSITORY and successor.node_type not in {
            NodeType.KNOWLEDGE_REPOSITORY,
            NodeType.PARENT_ORGANIZATION,
        }:
            raise InvariantError("repository knowledge passes to another repository or to its parent organization")
        node.status = NodeStatus.RETIRED
        node.successor_id = successor.identifier
        node.retired_on = on or date.today()
        self.events.append(
            DomainEvent(
                "NodeRetired",
                {"node_id": str(node_id), "successor": str(successor.identifier), "reason": reason},
            )
        )
        return successor.identifier

    # ------------------------------------------------------------ queries
    def get(self, node_id: NodeIdentifier) -> Node:
        return self._require_node(node_id)

    def children_of(self, node_id: NodeIdentifier) -> list[Node]:
        return [n for n in self._nodes.values() if n.parent_id == node_id]

    def active_children_of(self, node_id: NodeIdentifier) -> list[Node]:
        return [n for n in self.children_of(node_id) if n.is_active]

    def active_nodes(self) -> list[Node]:
        return [n for n in self._nodes.values() if n.is_active]

    def root(self) -> Node:
        for node in self._nodes.values():
            if node.parent_id is None:
                return node
        raise NotFoundError("organization has no root")

    def ancestors(self, node_id: NodeIdentifier) -> list[Node]:
        """Nearest first: parent, grandparent, ..., root."""
        out: list[Node] = []
        cursor = self._require_node(node_id)
        while cursor.parent_id is not None:
            cursor = self._require_node(cursor.parent_id)
            out.append(cursor)
        return out

    def path(self, node_id: NodeIdentifier) -> list[NodeIdentifier]:
        """Root → node."""
        chain = [n.identifier for n in reversed(self.ancestors(node_id))]
        return [*chain, node_id]

    def path_string(self, node_id: NodeIdentifier) -> str:
        return " > ".join(str(n) for n in self.path(node_id))

    def depth(self, node_id: NodeIdentifier) -> int:
        """Edges from the root (root = 0). Differs from layer for N-LIB (depth 2, L4)."""
        return len(self.ancestors(node_id))

    def descendants(self, node_id: NodeIdentifier, *, active_only: bool = False) -> list[Node]:
        out: list[Node] = []
        queue = deque(self.children_of(node_id))
        while queue:
            node = queue.popleft()
            if active_only and not node.is_active:
                continue
            out.append(node)
            queue.extend(self.children_of(node.identifier))
        return out

    def leaves(self) -> list[Node]:
        """Active nodes without active children."""
        return [n for n in self.active_nodes() if not self.active_children_of(n.identifier)]

    def max_depth(self) -> int:
        return max((self.depth(n.identifier) for n in self.active_nodes()), default=0)

    def nodes_on_layer(self, index: int) -> list[Node]:
        return [n for n in self.active_nodes() if n.layer.value == index]

    def is_ancestor(self, ancestor_id: NodeIdentifier, node_id: NodeIdentifier) -> bool:
        return any(a.identifier == ancestor_id for a in self.ancestors(node_id))

    def lowest_common_ancestor(self, *node_ids: NodeIdentifier) -> NodeIdentifier:
        if not node_ids:
            raise InvariantError("need at least one node")
        common = self.path(node_ids[0])
        for nid in node_ids[1:]:
            other = self.path(nid)
            prefix: list[NodeIdentifier] = []
            for a, b in zip(common, other):
                if a != b:
                    break
                prefix.append(a)
            common = prefix
        if not common:
            raise InvariantError("nodes do not share a root")
        return common[-1]

    def _require_active(self, node_id: NodeIdentifier) -> Node:
        node = self._require_node(node_id)
        if not node.is_active:
            raise InvariantError(f"node {node_id} is retired")
        return node

    def all_nodes(self) -> list[Node]:
        return list(self._nodes.values())

    def __contains__(self, node_id: NodeIdentifier) -> bool:
        return node_id.value in self._nodes

    def _require_node(self, node_id: NodeIdentifier) -> Node:
        node = self._nodes.get(node_id.value)
        if node is None:
            raise NotFoundError(f"unknown node {node_id}")
        return node

    def _assert_parent_child(self, parent: Node, child: Node) -> None:
        if parent.is_leaf:
            raise InvariantError(f"leaf node {parent.identifier} cannot have children")
        if parent.layer.value == child.layer.value:
            raise InvariantError(
                f"parent {parent.identifier} and child {child.identifier} share layer {parent.layer}"
            )
        adjacent = parent.layer.is_adjacent_parent_of(child.layer)
        exempt = any(e.allows(parent, child) for e in self.exemptions)
        if not adjacent and not exempt:
            raise InvariantError(
                f"parent layer {parent.layer} is not adjacent to child layer {child.layer}"
            )
        # Cycle check: walk from parent toward the root; child must not appear.
        seen: set[str] = set()
        cursor: Node | None = parent
        while cursor is not None:
            if cursor.identifier == child.identifier:
                raise InvariantError("parent–child relation would create a cycle")
            if cursor.identifier.value in seen:
                raise InvariantError("existing cycle detected in the tree")
            seen.add(cursor.identifier.value)
            cursor = self._nodes.get(cursor.parent_id.value) if cursor.parent_id else None
