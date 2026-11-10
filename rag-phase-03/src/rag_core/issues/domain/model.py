"""Issue aggregate (with SubIssue entities) and ProjectRecord."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from rag_core.shared_kernel.errors import InvariantError, NotFoundError
from rag_core.shared_kernel.events import DomainEvent
from rag_core.shared_kernel.identifiers import IssueId, NodeIdentifier, ProjectId


class IssueStatus(StrEnum):
    NEW = "new"
    ANALYSING = "analysing"
    KNOWLEDGE_IDENTIFIED = "knowledge_identified"
    EXECUTOR_IDENTIFIED = "executor_identified"
    SOLUTION_PROPOSED = "solution_proposed"
    IN_PROGRESS = "in_progress"
    AWAITING_DECISION = "awaiting_decision"
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    ARCHIVED = "archived"


_RESOLVED_LIKE = {IssueStatus.RESOLVED, IssueStatus.ARCHIVED}


@dataclass(frozen=True)
class ProgressPercentage:
    """Integer or decimal progress in [0, 100]."""

    value: Decimal

    def __post_init__(self) -> None:
        amount = self.value if isinstance(self.value, Decimal) else Decimal(self.value)
        object.__setattr__(self, "value", amount)
        if amount < 0 or amount > 100:
            raise InvariantError(f"ProgressPercentage must be in [0, 100], got {amount}")

    def __int__(self) -> int:
        return int(self.value)

    @classmethod
    def from_int(cls, value: int) -> ProgressPercentage:
        return cls(Decimal(value))


@dataclass(frozen=True)
class PriorityScore:
    value: Decimal

    def __post_init__(self) -> None:
        amount = self.value if isinstance(self.value, Decimal) else Decimal(self.value)
        if amount < 0:
            raise InvariantError("PriorityScore cannot be negative")
        object.__setattr__(self, "value", amount)


@dataclass
class SubIssue:
    identifier: IssueId
    title: str
    status: IssueStatus
    position: int
    explicit_progress: ProgressPercentage | None = None

    def __post_init__(self) -> None:
        if not self.identifier.is_subissue:
            raise InvariantError(f"{self.identifier} is not a sub-issue id")
        if not self.title.strip():
            raise InvariantError("sub-issue title is required")
        if self.position < 1:
            raise InvariantError("sub-issue position must be >= 1")

    def progress(self) -> ProgressPercentage:
        if self.status in _RESOLVED_LIKE:
            return ProgressPercentage.from_int(100)
        if self.explicit_progress is not None:
            return self.explicit_progress
        return ProgressPercentage.from_int(0)


@dataclass
class Issue:
    """Aggregate root. Progress is always recalculated through the root."""

    identifier: IssueId
    title: str
    owning_node: NodeIdentifier
    status: IssueStatus = IssueStatus.NEW
    project_id: ProjectId | None = None
    explicit_progress: ProgressPercentage | None = None
    urgency: int = 0
    risk: int = 0
    dependents: int = 0
    subissues: list[SubIssue] = field(default_factory=list)
    events: list[DomainEvent] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.identifier.is_subissue:
            raise InvariantError("Issue root cannot have a sub-issue id")
        if not self.title.strip():
            raise InvariantError("issue title is required")
        for score in (self.urgency, self.risk, self.dependents):
            if score < 0 or score > 10:
                raise InvariantError("urgency, risk and dependents must be in [0, 10]")

    @classmethod
    def create(
        cls,
        identifier: IssueId,
        title: str,
        owning_node: NodeIdentifier,
        **kwargs: object,
    ) -> Issue:
        issue = cls(identifier=identifier, title=title, owning_node=owning_node, **kwargs)  # type: ignore[arg-type]
        issue.events.append(DomainEvent("IssueCreated", {"issue_id": str(identifier)}))
        return issue

    def add_subissue(self, subissue: SubIssue) -> None:
        parent = subissue.identifier.parent_id
        if parent != self.identifier:
            raise InvariantError(
                f"sub-issue {subissue.identifier} does not belong to {self.identifier}"
            )
        if any(s.identifier == subissue.identifier for s in self.subissues):
            raise InvariantError(f"duplicate sub-issue {subissue.identifier}")
        if any(s.position == subissue.position for s in self.subissues):
            raise InvariantError(f"duplicate sub-issue position {subissue.position}")
        self.subissues.append(subissue)
        self.subissues.sort(key=lambda s: s.position)
        self.events.append(DomainEvent("IssueDecomposed", {"subissue_id": str(subissue.identifier)}))

    def subissue(self, identifier: IssueId) -> SubIssue:
        for sub in self.subissues:
            if sub.identifier == identifier:
                return sub
        raise NotFoundError(str(identifier))

    def progress(self) -> ProgressPercentage:
        if self.status in _RESOLVED_LIKE:
            return ProgressPercentage.from_int(100)
        if self.subissues:
            total = sum((s.progress().value for s in self.subissues), Decimal(0))
            mean = (total / Decimal(len(self.subissues))).quantize(Decimal("0.01"))
            return ProgressPercentage(mean)
        if self.explicit_progress is not None:
            return self.explicit_progress
        return ProgressPercentage.from_int(0)

    def priority(self) -> PriorityScore:
        """Deterministic ranking: 3*urgency + 2*risk + dependents."""
        value = Decimal(3 * self.urgency + 2 * self.risk + self.dependents)
        return PriorityScore(value)


def rank_issues(issues: list[Issue]) -> list[Issue]:
    """Stable sort: higher priority first, IssueId as tie-breaker."""
    return sorted(issues, key=lambda i: (-i.priority().value, i.identifier.value))


@dataclass
class ProjectRecord:
    """Supporting aggregate kept inside Issue Management (no 11th context)."""

    identifier: ProjectId
    title: str
    owning_node: NodeIdentifier
    related_issue_ids: tuple[IssueId, ...] = ()
    completion_percent: ProgressPercentage = field(default_factory=lambda: ProgressPercentage.from_int(0))

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise InvariantError("project title is required")
