"""Per-node IKE graph: typed relations only, no ownership of the endpoints."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.events import DomainEvent
from rag_core.shared_kernel.identifiers import NodeIdentifier


class RelationType(StrEnum):
    RELATES_TO = "relates_to"
    CAN_HANDLE = "can_handle"
    EVIDENCE_FOR = "evidence_for"
    KNOWLEDGE_LACK = "knowledge_lack"


@dataclass(frozen=True)
class RelationConfidence:
    value: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise InvariantError(f"RelationConfidence must be in [0, 1], got {self.value}")


@dataclass(frozen=True)
class IkeRelation:
    source_id: str
    target_id: str
    relation_type: RelationType
    confidence: RelationConfidence
    source_note: str = ""

    def __post_init__(self) -> None:
        if not self.source_id or not self.target_id:
            raise InvariantError("IKE relation endpoints are required")
        if self.source_id == self.target_id:
            raise InvariantError("IKE relation cannot be reflexive")


@dataclass
class IkeGraph:
    """Aggregate root: the relation graph of one node."""

    node_id: NodeIdentifier
    relations: list[IkeRelation] = field(default_factory=list)
    events: list[DomainEvent] = field(default_factory=list)

    def add(self, relation: IkeRelation) -> None:
        key = (relation.source_id, relation.target_id, relation.relation_type)
        if any((r.source_id, r.target_id, r.relation_type) == key for r in self.relations):
            raise InvariantError("duplicate IKE relation")
        self.relations.append(relation)
        name = "KnowledgeLackFlagged" if relation.relation_type is RelationType.KNOWLEDGE_LACK else "RelationCreated"
        self.events.append(DomainEvent(name, {"source": relation.source_id, "target": relation.target_id}))
