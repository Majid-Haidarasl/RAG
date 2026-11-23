"""Anti-corruption layer: Phase 6 ``Organization`` → processing ``TreeNode`` views."""

from __future__ import annotations

from rag_core.hierarchy.domain.model import NodeType, Organization
from rag_core.processing.domain.plan import TreeNode


def tree_nodes(org: Organization) -> list[TreeNode]:
    return [
        TreeNode(
            node_id=str(n.identifier),
            layer=n.layer.value,
            parent_id=str(n.parent_id) if n.parent_id is not None else None,
            active=n.is_active,
            repository=n.node_type is NodeType.KNOWLEDGE_REPOSITORY,
        )
        for n in org.all_nodes()
    ]
