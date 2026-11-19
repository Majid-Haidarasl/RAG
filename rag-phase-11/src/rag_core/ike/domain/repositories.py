from __future__ import annotations

from typing import Protocol

from rag_core.ike.domain.model import IkeGraph
from rag_core.shared_kernel.identifiers import NodeIdentifier


class IkeGraphRepository(Protocol):
    def get(self, node_id: NodeIdentifier) -> IkeGraph: ...
    def save(self, graph: IkeGraph) -> None: ...
