from __future__ import annotations

from rag_core.ike.domain.model import IkeGraph
from rag_core.shared_kernel.identifiers import NodeIdentifier


class InMemoryIkeGraphRepository:
    """``IkeGraphRepository``: one graph per node; unknown nodes get an empty graph."""

    def __init__(self) -> None:
        self._graphs: dict[str, IkeGraph] = {}

    def get(self, node_id: NodeIdentifier) -> IkeGraph:
        return self._graphs.get(str(node_id)) or IkeGraph(node_id)

    def save(self, graph: IkeGraph) -> None:
        self._graphs[str(graph.node_id)] = graph

    def __len__(self) -> int:
        return len(self._graphs)
