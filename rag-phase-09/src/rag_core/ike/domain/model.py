"""Per-node IKE graph: typed relations only, no ownership of the endpoints.

Phase 3 defined the relation value object and the graph aggregate. Phase 9
adds the relation model used by the builder:

* endpoint kinds, recognised from the identifier shape
  (``AR-ISS-024`` issue, ``AR-ISS-024/HW`` sub-issue, ``EX-…`` executor,
  ``AR-XXX-NNN`` knowledge document, anything else a topic / gap label);
* allowed (source kind → target kind) pairs per relation type;
* ``DEPENDS_ON`` (sub-issue → sibling) and ``PART_OF`` (sub-issue → parent);
* queries (outgoing / incoming / by type), counts, validation and a
  dependency-cycle check.

``add`` stays permissive (Phase 3 behaviour: only duplicate and reflexive
relations are rejected); ``add_checked`` also enforces the kind rules.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum
import re

from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.events import DomainEvent
from rag_core.shared_kernel.identifiers import NodeIdentifier


class RelationType(StrEnum):
    RELATES_TO = "relates_to"
    CAN_HANDLE = "can_handle"
    EVIDENCE_FOR = "evidence_for"
    KNOWLEDGE_LACK = "knowledge_lack"
    DEPENDS_ON = "depends_on"
    PART_OF = "part_of"


class EndpointKind(StrEnum):
    ISSUE = "issue"
    SUBISSUE = "subissue"
    EXECUTOR = "executor"
    KNOWLEDGE = "knowledge"
    TOPIC = "topic"


_SUBISSUE_RE = re.compile(r"^AR-ISS-\d{3}/[A-Z0-9]+$")
_ISSUE_RE = re.compile(r"^AR-ISS-\d{3}$")
_EXECUTOR_RE = re.compile(r"^EX-[A-Z0-9]+(?:-[A-Z0-9]+)*$")
_KNOWLEDGE_RE = re.compile(r"^AR-[A-Z]{2,5}-\d{2,4}(?:-\d{2,4})?$")


def endpoint_kind(identifier: str) -> EndpointKind:
    if _SUBISSUE_RE.match(identifier):
        return EndpointKind.SUBISSUE
    if _ISSUE_RE.match(identifier):
        return EndpointKind.ISSUE
    if _EXECUTOR_RE.match(identifier):
        return EndpointKind.EXECUTOR
    if _KNOWLEDGE_RE.match(identifier):
        return EndpointKind.KNOWLEDGE
    return EndpointKind.TOPIC


_K = EndpointKind
RELATION_RULES: dict[
    RelationType, tuple[frozenset[EndpointKind], frozenset[EndpointKind]]
] = {
    RelationType.RELATES_TO: (
        frozenset({_K.ISSUE, _K.SUBISSUE}),
        frozenset({_K.KNOWLEDGE, _K.ISSUE}),
    ),
    RelationType.CAN_HANDLE: (
        frozenset({_K.EXECUTOR}),
        frozenset({_K.ISSUE, _K.SUBISSUE}),
    ),
    RelationType.EVIDENCE_FOR: (
        frozenset({_K.KNOWLEDGE, _K.ISSUE}),
        frozenset({_K.EXECUTOR, _K.ISSUE, _K.SUBISSUE}),
    ),
    RelationType.KNOWLEDGE_LACK: (
        frozenset({_K.ISSUE, _K.SUBISSUE}),
        frozenset({_K.KNOWLEDGE, _K.ISSUE, _K.TOPIC}),
    ),
    RelationType.DEPENDS_ON: (frozenset({_K.SUBISSUE}), frozenset({_K.SUBISSUE})),
    RelationType.PART_OF: (frozenset({_K.SUBISSUE}), frozenset({_K.ISSUE})),
}


@dataclass(frozen=True)
class RelationConfidence:
    value: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise InvariantError(
                f"RelationConfidence must be in [0, 1], got {self.value}"
            )


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

    @property
    def key(self) -> tuple[str, str, RelationType]:
        return (self.source_id, self.target_id, self.relation_type)

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source_id,
            "target": self.target_id,
            "type": self.relation_type.value,
            "confidence": round(self.confidence.value, 4),
            "note": self.source_note,
        }


def relation_problems(relation: IkeRelation) -> list[str]:
    """Kind rules for one relation; an empty list means the relation is well-typed."""
    problems: list[str] = []
    sources, targets = RELATION_RULES[relation.relation_type]
    sk, tk = endpoint_kind(relation.source_id), endpoint_kind(relation.target_id)
    label = (
        f"{relation.relation_type.value} {relation.source_id} -> {relation.target_id}"
    )
    if sk not in sources:
        problems.append(f"{label}: source kind {sk.value} not allowed")
    if tk not in targets:
        problems.append(f"{label}: target kind {tk.value} not allowed")
    if (
        relation.relation_type is RelationType.DEPENDS_ON
        and sk is tk is EndpointKind.SUBISSUE
    ):
        if relation.source_id.split("/", 1)[0] != relation.target_id.split("/", 1)[0]:
            problems.append(f"{label}: dependencies must stay inside one issue")
    if relation.relation_type is RelationType.PART_OF and sk is EndpointKind.SUBISSUE:
        if relation.source_id.split("/", 1)[0] != relation.target_id:
            problems.append(f"{label}: a sub-issue is part of its own parent only")
    return problems


@dataclass
class IkeGraph:
    """Aggregate root: the relation graph of one node."""

    node_id: NodeIdentifier
    relations: list[IkeRelation] = field(default_factory=list)
    events: list[DomainEvent] = field(default_factory=list)

    def has(self, source_id: str, target_id: str, relation_type: RelationType) -> bool:
        key = (source_id, target_id, relation_type)
        return any(r.key == key for r in self.relations)

    def add(self, relation: IkeRelation) -> None:
        if self.has(*relation.key):
            raise InvariantError("duplicate IKE relation")
        self.relations.append(relation)
        name = (
            "KnowledgeLackFlagged"
            if relation.relation_type is RelationType.KNOWLEDGE_LACK
            else "RelationCreated"
        )
        self.events.append(
            DomainEvent(
                name, {"source": relation.source_id, "target": relation.target_id}
            )
        )

    def add_checked(self, relation: IkeRelation) -> None:
        problems = relation_problems(relation)
        if problems:
            raise InvariantError("; ".join(problems))
        self.add(relation)

    def add_if_absent(self, relation: IkeRelation) -> bool:
        """``add_checked`` unless the same (source, target, type) exists; True when added."""
        if self.has(*relation.key):
            return False
        self.add_checked(relation)
        return True

    # ------------------------------------------------------------ queries
    def outgoing(
        self, source_id: str, relation_type: RelationType | None = None
    ) -> list[IkeRelation]:
        return [
            r
            for r in self.relations
            if r.source_id == source_id
            and (relation_type is None or r.relation_type is relation_type)
        ]

    def incoming(
        self, target_id: str, relation_type: RelationType | None = None
    ) -> list[IkeRelation]:
        return [
            r
            for r in self.relations
            if r.target_id == target_id
            and (relation_type is None or r.relation_type is relation_type)
        ]

    def of_type(self, relation_type: RelationType) -> list[IkeRelation]:
        return [r for r in self.relations if r.relation_type is relation_type]

    def counts(self) -> dict[str, int]:
        c = Counter(r.relation_type.value for r in self.relations)
        return {t.value: c.get(t.value, 0) for t in RelationType}

    def endpoints(self) -> dict[str, int]:
        ids = {r.source_id for r in self.relations} | {
            r.target_id for r in self.relations
        }
        c = Counter(endpoint_kind(i).value for i in ids)
        return {k.value: c.get(k.value, 0) for k in EndpointKind}

    def dependency_cycle(self) -> list[str]:
        edges: dict[str, list[str]] = {}
        for r in self.of_type(RelationType.DEPENDS_ON):
            edges.setdefault(r.source_id, []).append(r.target_id)
        state: dict[str, int] = {}

        def visit(node: str, path: list[str]) -> list[str]:
            state[node] = 1
            for nxt in edges.get(node, []):
                if state.get(nxt) == 1:
                    return [*path, node, nxt]
                if state.get(nxt) is None:
                    found = visit(nxt, [*path, node])
                    if found:
                        return found
            state[node] = 2
            return []

        for start in sorted(edges):
            if state.get(start) is None:
                found = visit(start, [])
                if found:
                    return found
        return []

    def validate(self) -> list[str]:
        problems: list[str] = []
        seen: set[tuple[str, str, RelationType]] = set()
        for r in self.relations:
            if r.key in seen:
                problems.append(
                    f"duplicate relation {r.relation_type.value} {r.source_id} -> {r.target_id}"
                )
            seen.add(r.key)
            problems.extend(relation_problems(r))
        cycle = self.dependency_cycle()
        if cycle:
            problems.append("dependency cycle " + " -> ".join(cycle))
        return problems

    def to_dict(self) -> dict[str, object]:
        return {
            "node": str(self.node_id),
            "counts": self.counts(),
            "endpoints": self.endpoints(),
            "relations": [r.to_dict() for r in self.relations],
        }
