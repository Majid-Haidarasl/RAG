"""Research and knowledge gaps: what is missing, where, and how serious it is.

A ``Gap`` is produced by a ``GapRule`` from plain read models (``GapInputs``)
that the infrastructure ACLs copy out of the other contexts:

* project tracking records and the scorecard (Phase 12 projects context);
* issues and sub-issues (Phase 7) with their status and dependencies;
* IKE leads and knowledge lacks per sub-issue (Phase 9).

Gap ids are stable: ``<RULE>:<subject>`` (for example ``DEP:AR-ISS-024/WIN``),
so the same input always gives the same gaps in the same order.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from rag_core.shared_kernel.errors import InvariantError

CLOSED_STATUSES = frozenset({"resolved", "closed"})


class GapKind(StrEnum):
    RESEARCH = "research"                  # an open research question (AR-TRN-026 section 9)
    KNOWLEDGE = "knowledge"                # IKE knowledge lack on an active sub-issue
    EXECUTOR = "executor"                  # active sub-issue without a lead or executor
    DEPENDENCY = "dependency"              # blocked by an unresolved sibling sub-issue
    CHALLENGE = "challenge"                # a challenge not linked to any issue (no owner path)
    MEASUREMENT = "measurement"            # scorecard dimension without measured evidence
    STALE = "stale"                        # unsolved-issue record whose issues are all closed
    EVIDENCE = "evidence"                  # a record without evidence


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


SEVERITY_ORDER = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}


@dataclass(frozen=True)
class Gap:
    gap_id: str
    rule: str
    kind: GapKind
    severity: Severity
    subject: str
    title_en: str
    title_fa: str
    issue_id: str = ""
    nodes: tuple[str, ...] = ()
    documents: tuple[str, ...] = ()
    detail: str = ""

    def __post_init__(self) -> None:
        if not self.gap_id.strip() or not self.subject.strip():
            raise InvariantError("a gap needs an id and a subject")
        if not isinstance(self.kind, GapKind):
            object.__setattr__(self, "kind", GapKind(self.kind))
        if not isinstance(self.severity, Severity):
            object.__setattr__(self, "severity", Severity(self.severity))

    def title(self, language: str) -> str:
        return self.title_fa if language == "fa" else self.title_en

    def to_dict(self) -> dict[str, object]:
        return {"gap_id": self.gap_id, "rule": self.rule, "kind": self.kind.value, "severity": self.severity.value,
                "subject": self.subject, "issue_id": self.issue_id, "title_en": self.title_en,
                "title_fa": self.title_fa, "nodes": list(self.nodes), "documents": list(self.documents),
                "detail": self.detail}


# ---- read models (filled by the infrastructure ACLs) -------------------------------------
@dataclass(frozen=True)
class RecordView:
    record_id: str
    kind: str
    state: str
    title_en: str
    title_fa: str
    issues: tuple[str, ...] = ()
    nodes: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    people: tuple[str, ...] = ()
    validated_result: bool = False


@dataclass(frozen=True)
class SubIssueView:
    item_id: str
    issue_id: str
    title_en: str
    title_fa: str
    status: str
    owner_node: str = ""
    executors: tuple[str, ...] = ()
    lead: str = ""
    lacks: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()     # sibling ids, e.g. ("AR-ISS-024/HW",)
    documents: tuple[str, ...] = ()

    @property
    def active(self) -> bool:
        return self.status not in CLOSED_STATUSES


@dataclass(frozen=True)
class IssueStateView:
    issue_id: str
    status: str
    title_en: str = ""
    title_fa: str = ""

    @property
    def active(self) -> bool:
        return self.status not in CLOSED_STATUSES


@dataclass(frozen=True)
class DimensionView:
    dimension_id: str
    name_en: str
    name_fa: str
    state: str
    evidence: tuple[str, ...] = ()
    research: str = ""


@dataclass(frozen=True)
class GapInputs:
    records: tuple[RecordView, ...] = ()
    subissues: tuple[SubIssueView, ...] = ()
    issues: tuple[IssueStateView, ...] = ()
    scorecard: tuple[DimensionView, ...] = ()
    as_of: date | None = None
    extra: dict[str, str] = field(default_factory=dict)

    def issue(self, issue_id: str) -> IssueStateView | None:
        return next((i for i in self.issues if i.issue_id == issue_id), None)

    def subissue(self, item_id: str) -> SubIssueView | None:
        return next((s for s in self.subissues if s.item_id == item_id), None)
