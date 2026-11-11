"""Hierarchy aggregates: LayerRegistry (as Organization.layers) and Organization."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from rag_core.shared_kernel.confidentiality import Confidentiality
from rag_core.shared_kernel.errors import InvariantError, NotFoundError
from rag_core.shared_kernel.events import DomainEvent
from rag_core.shared_kernel.identifiers import NodeIdentifier
from rag_core.shared_kernel.layer import LayerIndex

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

    def __post_init__(self) -> None:
        expected = self.index.code
        if self.code != expected:
            raise InvariantError(f"layer code {self.code!r} must equal {expected}")
        if not self.name_en or not self.name_fa:
            raise InvariantError("layer needs bilingual names")


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
            self._assert_parent_child(parent, node)
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

    def get(self, node_id: NodeIdentifier) -> Node:
        return self._require_node(node_id)

    def children_of(self, node_id: NodeIdentifier) -> list[Node]:
        return [n for n in self._nodes.values() if n.parent_id == node_id]

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
        repository_exemption = child.node_type == NodeType.KNOWLEDGE_REPOSITORY
        if not adjacent and not repository_exemption:
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
