"""Project tracking model: projects, tracking records and the interim knowledge scorecard.

Source: AR-TRN-026 sections 7-9 (projects of the year, achievements and
challenges, the annual knowledge scorecard and the two open research gaps)
and AR-FIN-008 (remaining value and physical progress at the end of
Shahrivar 1403).

Rules that come straight from the corpus:

* an achievement is ``recorded`` or ``conditional`` (never ``open``) and
  must cite evidence; no completed-project claim is made;
* a research record stays ``open`` or ``conditional`` and may not claim a
  validated result (no validated model, no superiority claim);
* an unsolved issue links at least one registered issue and stays open;
* every achievement and challenge (a "lesson") keeps its applicability
  conditions, so a project-specific observation does not become a
  universal rule;
* targets are plans, not results: the scorecard uses recorded /
  conditional / open states, never numerical grades.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.identifiers import ProjectId


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    AT_RISK = "at_risk"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"


class RecordKind(StrEnum):
    RESEARCH = "research"
    ACHIEVEMENT = "achievement"
    CHALLENGE = "challenge"
    UNSOLVED_ISSUE = "unsolved_issue"


class ClaimState(StrEnum):
    """AR-TRN-026 section 8: recorded, conditional and open states instead of grades."""

    RECORDED = "recorded"
    CONDITIONAL = "conditional"
    OPEN = "open"


RECORD_KINDS: tuple[str, ...] = tuple(k.value for k in RecordKind)
LESSON_KINDS = frozenset({RecordKind.ACHIEVEMENT, RecordKind.CHALLENGE})


@dataclass(frozen=True)
class Project:
    project_id: str
    name_en: str
    name_fa: str
    owner_node: str
    progress_percent: int
    status: ProjectStatus = ProjectStatus.ACTIVE
    customer: str = ""
    code_source: str = "registry"
    nodes: tuple[str, ...] = ()
    contract_ref: str = ""
    contract_value_mtoman: int | None = None
    remaining_mtoman: int | None = None
    primary_issue: str = ""
    issues: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "project_id", str(ProjectId(self.project_id)))
        if not self.name_en.strip() or not self.name_fa.strip():
            raise InvariantError(
                f"{self.project_id}: project needs an English and a Persian name"
            )
        if not 0 <= int(self.progress_percent) <= 100:
            raise InvariantError(
                f"{self.project_id}: progress must be in [0, 100], got {self.progress_percent}"
            )
        for label, value in (
            ("remaining", self.remaining_mtoman),
            ("contract value", self.contract_value_mtoman),
        ):
            if value is not None and value < 0:
                raise InvariantError(f"{self.project_id}: {label} cannot be negative")
        if (
            self.contract_value_mtoman is not None
            and self.remaining_mtoman is not None
            and self.remaining_mtoman > self.contract_value_mtoman
        ):
            raise InvariantError(
                f"{self.project_id}: remaining value is larger than the contract value"
            )
        if self.primary_issue and self.primary_issue not in self.issues:
            raise InvariantError(
                f"{self.project_id}: primary issue {self.primary_issue} is not in its issue list"
            )
        if not isinstance(self.status, ProjectStatus):
            object.__setattr__(self, "status", ProjectStatus(self.status))
        if self.status is ProjectStatus.COMPLETED and self.progress_percent < 100:
            raise InvariantError(
                f"{self.project_id}: a completed project must be at 100% progress"
            )

    @property
    def all_nodes(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys([self.owner_node, *self.nodes]))

    def numbers(self) -> dict[str, int]:
        """Numeric facts that must be found in the evidence documents."""
        out = {"progress_percent": int(self.progress_percent)}
        if self.remaining_mtoman is not None:
            out["remaining_mtoman"] = int(self.remaining_mtoman)
        if self.contract_value_mtoman is not None:
            out["contract_value_mtoman"] = int(self.contract_value_mtoman)
        return out


@dataclass(frozen=True)
class TrackRecord:
    """One research item, achievement, challenge or unsolved issue."""

    record_id: str
    kind: RecordKind
    state: ClaimState
    title_en: str
    title_fa: str
    statement_en: str = ""
    statement_fa: str = ""
    conditions: str = ""
    project: str = ""
    nodes: tuple[str, ...] = ()
    people: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    validated_result: bool = False
    risks: tuple[str, ...] = ()
    evidence_needed: tuple[str, ...] = ()
    measures: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.record_id.strip():
            raise InvariantError("record id is required")
        if not isinstance(self.kind, RecordKind):
            object.__setattr__(self, "kind", RecordKind(self.kind))
        if not isinstance(self.state, ClaimState):
            object.__setattr__(self, "state", ClaimState(self.state))
        if not self.title_en.strip() or not self.title_fa.strip():
            raise InvariantError(
                f"{self.record_id}: record needs an English and a Persian title"
            )

    @property
    def is_lesson(self) -> bool:
        return self.kind in LESSON_KINDS

    def statement(self, language: str) -> str:
        return self.statement_fa if language == "fa" else self.statement_en

    def title(self, language: str) -> str:
        return self.title_fa if language == "fa" else self.title_en


@dataclass(frozen=True)
class ScorecardDimension:
    dimension_id: str
    name_en: str
    name_fa: str
    state: ClaimState
    target_en: str = ""
    owner: str = ""
    evidence: tuple[str, ...] = ()
    research: str = ""

    def __post_init__(self) -> None:
        if not self.dimension_id.strip():
            raise InvariantError("scorecard dimension id is required")
        if not isinstance(self.state, ClaimState):
            object.__setattr__(self, "state", ClaimState(self.state))


@dataclass(frozen=True)
class ProjectRegistry:
    """The whole tracking registry of one cycle."""

    cycle: str
    cutoff: str
    projects: tuple[Project, ...] = ()
    records: tuple[TrackRecord, ...] = ()
    scorecard: tuple[ScorecardDimension, ...] = ()

    def project(self, project_id: str) -> Project | None:
        return next((p for p in self.projects if p.project_id == project_id), None)

    def record(self, record_id: str) -> TrackRecord | None:
        return next((r for r in self.records if r.record_id == record_id), None)

    def records_of(
        self, kind: RecordKind | str, project: str | None = None
    ) -> tuple[TrackRecord, ...]:
        wanted = RecordKind(kind)
        return tuple(
            r
            for r in self.records
            if r.kind is wanted and (project is None or r.project == project)
        )

    def counts_by_kind(self) -> dict[str, int]:
        out = {k: 0 for k in RECORD_KINDS}
        for r in self.records:
            out[r.kind.value] += 1
        return out

    def project_of_issue(self, issue_id: str) -> tuple[Project, ...]:
        return tuple(p for p in self.projects if issue_id in p.issues)
