"""Bottom-up processing plan over the node tree.

Rules (AR-TRN-026 §1 and §6, layer registry ``transfer_direction``):

* every active node with an active parent sends one package to its parent;
* deeper nodes come first (post-order: a parent is processed only after all
  its children), ties ordered by node id, so the order is deterministic;
* the root (Board, L0) only receives — its resolutions go down, not up;
* the knowledge repository (L4 library) is a peer of L3: it indexes evidence
  and does not summarize upward on its own;
* retired nodes and nodes under a retired parent are skipped.
"""

from __future__ import annotations

from dataclasses import dataclass

from rag_core.shared_kernel.errors import InvariantError

ROOT_REASON = "root: receives packages, hands resolutions down only"
REPOSITORY_REASON = "knowledge repository: indexes evidence, no upward package (AR-TRN-026 §1)"
RETIRED_REASON = "retired node"
PARENT_RETIRED_REASON = "parent is retired"


@dataclass(frozen=True)
class TreeNode:
    node_id: str
    layer: int
    parent_id: str | None
    active: bool = True
    repository: bool = False


@dataclass(frozen=True)
class ProcessingStep:
    order: int
    source_node: str
    target_node: str
    source_layer: int
    target_layer: int
    depth: int


@dataclass(frozen=True)
class SkippedNode:
    node_id: str
    reason: str


@dataclass(frozen=True)
class ProcessingPlan:
    steps: tuple[ProcessingStep, ...]
    skipped: tuple[SkippedNode, ...] = ()

    @property
    def senders(self) -> tuple[str, ...]:
        return tuple(s.source_node for s in self.steps)

    def step_of(self, node_id: str) -> ProcessingStep:
        for s in self.steps:
            if s.source_node == node_id:
                return s
        raise KeyError(node_id)

    def children_of(self, node_id: str) -> tuple[str, ...]:
        return tuple(s.source_node for s in self.steps if s.target_node == node_id)

    def is_bottom_up(self) -> bool:
        """Every sender comes after all senders that report to it."""
        order = {s.source_node: s.order for s in self.steps}
        return all(order[child] < s.order for s in self.steps for child in self.children_of(s.source_node))


def _depths(index: dict[str, TreeNode]) -> dict[str, int]:
    depths: dict[str, int] = {}
    for node_id in index:
        chain: list[str] = []
        current: str | None = node_id
        while current is not None and current not in depths:
            if current in chain:
                raise InvariantError("cycle in the node tree: " + " -> ".join([*chain, current]))
            chain.append(current)
            current = index[current].parent_id
        base = -1 if current is None else depths[current]
        for offset, n in enumerate(reversed(chain), 1):
            depths[n] = base + offset
    return depths


def build_plan(nodes: list[TreeNode] | tuple[TreeNode, ...]) -> ProcessingPlan:
    index: dict[str, TreeNode] = {}
    for n in nodes:
        if n.node_id in index:
            raise InvariantError(f"duplicate node {n.node_id}")
        index[n.node_id] = n
    roots = [n for n in index.values() if n.parent_id is None]
    if len(roots) != 1:
        raise InvariantError(f"the tree needs exactly one root, found {len(roots)}")
    for n in index.values():
        if n.parent_id is not None and n.parent_id not in index:
            raise InvariantError(f"{n.node_id}: unknown parent {n.parent_id}")
    depths = _depths(index)
    senders: list[TreeNode] = []
    skipped: list[SkippedNode] = []
    for n in sorted(index.values(), key=lambda x: (-depths[x.node_id], x.node_id)):
        if not n.active:
            skipped.append(SkippedNode(n.node_id, RETIRED_REASON))
        elif n.parent_id is None:
            skipped.append(SkippedNode(n.node_id, ROOT_REASON))
        elif n.repository:
            skipped.append(SkippedNode(n.node_id, REPOSITORY_REASON))
        elif not index[n.parent_id].active:
            skipped.append(SkippedNode(n.node_id, PARENT_RETIRED_REASON))
        else:
            senders.append(n)
    steps = tuple(
        ProcessingStep(order=k, source_node=n.node_id, target_node=str(n.parent_id), source_layer=n.layer,
                       target_layer=index[str(n.parent_id)].layer, depth=depths[n.node_id])
        for k, n in enumerate(senders, 1)
    )
    return ProcessingPlan(steps, tuple(skipped))
