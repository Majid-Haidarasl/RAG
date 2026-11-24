"""What the judge looks at: one output, its sources and what was expected."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from rag_core.judging.domain.rubric import OutputKind
from rag_core.shared_kernel.errors import InvariantError

REFUSAL_STATUSES = frozenset(
    {"out_of_scope", "insufficient_context", "not_found_in_scope", "not_found"}
)
NOT_FOUND_STATUSES = frozenset(
    {"insufficient_context", "not_found_in_scope", "not_found"}
)
GOLD_LABELS = frozenset({"", "accept", "reject"})


@dataclass(frozen=True)
class SourceBlock:
    """A block the judged output may rely on (a chunk, or the IKE fact list)."""

    label: str
    text: str
    document_id: str = ""
    order: int | None = None
    language: str | None = None


@dataclass(frozen=True)
class Expectation:
    """Reference information. Empty fields mean "not known"."""

    status: str = "answered"  # answered | out_of_scope | not_found | summary
    facts: tuple[
        tuple[str, ...], ...
    ] = ()  # key-fact groups (one alternative per group)
    escalation: str = ""  # expected escalation target (out_of_scope)
    items: tuple[str, ...] = ()  # sub-issue ids a summary must mention
    item_leads: tuple[
        tuple[str, tuple[str, ...]], ...
    ] = ()  # (sub-issue id, lead name alternatives)
    gaps: tuple[str, ...] = ()  # knowledge-lack targets a summary should mention


@dataclass(frozen=True)
class JudgeCase:
    case_id: str
    kind: OutputKind
    language: str
    task: str
    output: str
    sources: tuple[SourceBlock, ...] = ()
    expectation: Expectation = field(default_factory=Expectation)
    status: str = "answered"  # what the system produced: answered | out_of_scope | insufficient_context | ...
    escalation: str = ""  # escalation target the system produced
    node: str = ""
    origin: str = ""  # e.g. calibration, phase8-live, ike-template, ike-llm, negative:wrong_number
    gold: str = ""  # accept | reject | "" (unknown)
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise InvariantError("case_id is required")
        if self.language not in {"fa", "en"}:
            raise InvariantError(f"{self.case_id}: language must be fa or en")
        if self.gold not in GOLD_LABELS:
            raise InvariantError(
                f"{self.case_id}: gold must be accept, reject or empty"
            )
        if not isinstance(self.kind, OutputKind):
            object.__setattr__(self, "kind", OutputKind(self.kind))

    @property
    def is_negative(self) -> bool:
        return self.origin.startswith("negative:")

    @property
    def refused(self) -> bool:
        return self.status in REFUSAL_STATUSES

    def mutated(self, suffix: str, output: str, **changes: object) -> JudgeCase:
        return replace(
            self,
            case_id=f"{self.case_id}~{suffix}",
            output=output,
            origin=f"negative:{suffix}",
            gold="reject",
            **changes,
        )
