"""Issue aggregate (with SubIssue entities), relative position and ProjectRecord.

Phase 7 extends the Phase 3 model: issue metadata, the validated status state
machine (``status.py``), sub-issue dependencies, closure invariants and the
issue's relative position in the organization (via the ``OrgDirectory`` port).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum

from rag_core.issues.domain.ports import OrgDirectory
from rag_core.issues.domain.status import (
    INVALIDATING_RESOLUTIONS,
    IssueStatus,
    Resolution,
    StatusCategory,
    check_transition,
)
from rag_core.shared_kernel.errors import InvariantError, NotFoundError
from rag_core.shared_kernel.events import DomainEvent
from rag_core.shared_kernel.identifiers import DocumentId, IssueId, NodeIdentifier, ProjectId

__all__ = [
    "BOARD_THRESHOLD_MTOMAN",
    "CEO_THRESHOLD_MTOMAN",
    "ContractRef",
    "Issue",
    "IssueCategory",
    "IssueScope",
    "IssueStatus",
    "Priority",
    "PriorityScore",
    "ProgressPercentage",
    "ProjectRecord",
    "RelativePosition",
    "Resolution",
    "Severity",
    "StatusCategory",
    "SubIssue",
    "approval_authority",
    "rank_issues",
]

_RESOLVED_LIKE = {IssueStatus.RESOLVED, IssueStatus.CLOSED}
_CONTRACT_RE = re.compile(r"^AR-CNT-\d{4}-\d{3}$")

# AR-LEG-009: CEO approval above 500 million toman, Board approval above 2,000 million.
CEO_THRESHOLD_MTOMAN = 500
BOARD_THRESHOLD_MTOMAN = 2000


def approval_authority(amount_mtoman: int | None) -> str:
    """Who must approve a commitment of this size: ``unit``, ``ceo`` or ``board``."""
    if amount_mtoman is None or amount_mtoman <= CEO_THRESHOLD_MTOMAN:
        return "unit"
    if amount_mtoman <= BOARD_THRESHOLD_MTOMAN:
        return "ceo"
    return "board"


class IssueCategory(StrEnum):
    DELIVERY_DELAY = "delivery_delay"
    HARDWARE = "hardware"
    SOFTWARE = "software"
    CONTRACT = "contract"
    FINANCE = "finance"
    SUPPORT_INCIDENT = "support_incident"
    SCHEDULE = "schedule"
    PROCUREMENT = "procurement"
    HANDOVER = "handover"
    DESIGN = "design"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Priority(StrEnum):
    """AR-SW-022 priorities. P1 is a complete outage only; delay alone is not P1."""

    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


@dataclass(frozen=True)
class ContractRef:
    value: str

    def __post_init__(self) -> None:
        text = self.value.strip().upper()
        if not _CONTRACT_RE.match(text):
            raise InvariantError(f"contract reference must look like AR-CNT-1402-118, got {self.value!r}")
        object.__setattr__(self, "value", text)

    def __str__(self) -> str:
        return self.value


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
    """Entity inside the Issue aggregate; identity ``<parent>/<CODE>`` is the parent link."""

    identifier: IssueId
    title: str
    status: IssueStatus
    position: int
    explicit_progress: ProgressPercentage | None = None
    owner_node: NodeIdentifier | None = None
    supporting_nodes: tuple[NodeIdentifier, ...] = ()
    related_documents: tuple[DocumentId, ...] = ()
    depends_on: tuple[str, ...] = ()  # sibling suffixes, e.g. ("HW",)
    scope: str = ""
    title_fa: str = ""
    executors: tuple[str, ...] = ()
    acceptance_output: str = ""
    reserved_decision: bool = False
    resolution: Resolution | None = None
    history: list[tuple[str, str, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.identifier.is_subissue:
            raise InvariantError(f"{self.identifier} is not a sub-issue id")
        if not self.title.strip():
            raise InvariantError("sub-issue title is required")
        if self.position < 1:
            raise InvariantError("sub-issue position must be >= 1")
        if self.identifier.suffix in self.depends_on:
            raise InvariantError("a sub-issue cannot depend on itself")

    @property
    def parent_id(self) -> IssueId:
        parent = self.identifier.parent_id
        assert parent is not None
        return parent

    @property
    def code(self) -> str:
        suffix = self.identifier.suffix
        assert suffix is not None
        return suffix

    @property
    def nodes(self) -> tuple[NodeIdentifier, ...]:
        owner = (self.owner_node,) if self.owner_node else ()
        return owner + tuple(n for n in self.supporting_nodes if n != self.owner_node)

    def progress(self) -> ProgressPercentage:
        if self.status in _RESOLVED_LIKE:
            return ProgressPercentage.from_int(100)
        if self.explicit_progress is not None:
            return self.explicit_progress
        return ProgressPercentage.from_int(0)


class IssueScope(StrEnum):
    LOCAL = "local"  # every involved node is inside the owner's subtree
    CROSS_UNIT = "cross_unit"  # spans units under one deputy (L2)
    CROSS_DEPUTY = "cross_deputy"  # spans deputies: common ancestor is L1/L0


@dataclass(frozen=True)
class RelativePosition:
    owner: str
    owner_layer: int
    owner_depth: int
    owner_path: tuple[str, ...]
    involved: tuple[str, ...]
    common_ancestor: str
    common_ancestor_layer: int
    scope: IssueScope
    escalation_action: str
    escalation_target: str
    reason: str

    @property
    def is_local(self) -> bool:
        return self.scope is IssueScope.LOCAL

    @property
    def is_cross_unit(self) -> bool:
        return not self.is_local


@dataclass
class Issue:
    """Aggregate root. All sub-issue changes and progress go through the root."""

    identifier: IssueId
    title: str
    owning_node: NodeIdentifier
    status: IssueStatus = IssueStatus.OPEN
    project_id: ProjectId | None = None
    explicit_progress: ProgressPercentage | None = None
    urgency: int = 0
    risk: int = 0
    dependents: int = 0
    subissues: list[SubIssue] = field(default_factory=list)
    events: list[DomainEvent] = field(default_factory=list)
    # ---- Phase 7 metadata
    description: str = ""
    title_fa: str = ""
    description_fa: str = ""
    reporter_node: NodeIdentifier | None = None
    affected_nodes: tuple[NodeIdentifier, ...] = ()
    related_documents: tuple[DocumentId, ...] = ()
    contract_ref: ContractRef | None = None
    customer: str = ""
    category: IssueCategory = IssueCategory.SOFTWARE
    severity: Severity = Severity.MEDIUM
    priority_level: Priority = Priority.P3
    opened_on: date | None = None
    due_on: date | None = None
    tags: tuple[str, ...] = ()
    reserved_decision: bool = False
    decision_amount_mtoman: int | None = None
    resolution: Resolution | None = None
    duplicate_of: IssueId | None = None
    related_issues: tuple[IssueId, ...] = ()
    history: list[tuple[str, str, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.identifier.is_subissue:
            raise InvariantError("Issue root cannot have a sub-issue id")
        if not self.title.strip():
            raise InvariantError("issue title is required")
        for score in (self.urgency, self.risk, self.dependents):
            if score < 0 or score > 10:
                raise InvariantError("urgency, risk and dependents must be in [0, 10]")
        if self.opened_on and self.due_on and self.due_on < self.opened_on:
            raise InvariantError("due date cannot be before the opening date")
        if self.duplicate_of == self.identifier or self.identifier in self.related_issues:
            raise InvariantError("an issue cannot link to itself")
        if self.decision_amount_mtoman is not None and self.decision_amount_mtoman < 0:
            raise InvariantError("decision amount cannot be negative")
        self.tags = tuple(sorted({t.strip().lower() for t in self.tags if t.strip()}))

    # ------------------------------------------------------------ factory
    @classmethod
    def create(
        cls,
        identifier: IssueId,
        title: str,
        owning_node: NodeIdentifier,
        *,
        directory: OrgDirectory | None = None,
        **kwargs: object,
    ) -> Issue:
        issue = cls(identifier=identifier, title=title, owning_node=owning_node, **kwargs)  # type: ignore[arg-type]
        if directory is not None:
            issue.assert_nodes_exist(directory)
        issue.events.append(DomainEvent("IssueCreated", {"issue_id": str(identifier)}))
        return issue

    # ------------------------------------------------------------ metadata
    @property
    def nodes(self) -> tuple[NodeIdentifier, ...]:
        """Owner first, then affected nodes (no duplicates, stable order)."""
        seen: list[NodeIdentifier] = [self.owning_node]
        for n in self.affected_nodes:
            if n not in seen:
                seen.append(n)
        return tuple(seen)

    def all_node_ids(self) -> set[str]:
        ids = {str(n) for n in self.nodes}
        if self.reporter_node:
            ids.add(str(self.reporter_node))
        for sub in self.subissues:
            ids.update(str(n) for n in sub.nodes)
        return ids

    def assert_nodes_exist(self, directory: OrgDirectory) -> None:
        missing = sorted(n for n in self.all_node_ids() if not directory.exists(n))
        if missing:
            raise NotFoundError(f"unknown nodes for {self.identifier}: {', '.join(missing)}")

    @property
    def text(self) -> str:
        return " ".join(p for p in (self.title, self.title_fa, self.description, self.description_fa) if p)

    @property
    def is_reserved_decision(self) -> bool:
        return self.reserved_decision or approval_authority(self.decision_amount_mtoman) == "board"

    # ------------------------------------------------------------ sub-issues
    def add_subissue(self, subissue: SubIssue) -> None:
        parent = subissue.identifier.parent_id
        if parent != self.identifier:
            raise InvariantError(f"sub-issue {subissue.identifier} does not belong to {self.identifier}")
        if self.status is IssueStatus.CLOSED:
            raise InvariantError(f"{self.identifier} is closed; reopen it before adding sub-issues")
        if any(s.identifier == subissue.identifier for s in self.subissues):
            raise InvariantError(f"duplicate sub-issue {subissue.identifier}")
        if any(s.position == subissue.position for s in self.subissues):
            raise InvariantError(f"duplicate sub-issue position {subissue.position}")
        codes = {s.code for s in self.subissues} | {subissue.code}
        unknown = [d for d in subissue.depends_on if d not in codes]
        if unknown:
            raise InvariantError(f"{subissue.identifier} depends on unknown sibling(s) {unknown}")
        self.subissues.append(subissue)
        self.subissues.sort(key=lambda s: s.position)
        cycle = self.dependency_cycle()
        if cycle:
            self.subissues.remove(subissue)
            raise InvariantError(f"sub-issue dependencies form a cycle: {' -> '.join(cycle)}")
        self.events.append(DomainEvent("IssueDecomposed", {"subissue_id": str(subissue.identifier)}))

    def subissue(self, identifier: IssueId | str) -> SubIssue:
        key = identifier if isinstance(identifier, IssueId) else IssueId(
            identifier if "/" in str(identifier) else f"{self.identifier}/{identifier}"
        )
        for sub in self.subissues:
            if sub.identifier == key:
                return sub
        raise NotFoundError(str(key))

    def dependency_cycle(self) -> list[str]:
        """Return one cycle among sub-issue dependencies (empty list if none)."""
        graph = {s.code: list(s.depends_on) for s in self.subissues}
        state: dict[str, int] = {}
        stack: list[str] = []

        def visit(code: str) -> list[str]:
            state[code] = 1
            stack.append(code)
            for nxt in graph.get(code, []):
                if state.get(nxt) == 1:
                    return stack[stack.index(nxt):] + [nxt]
                if nxt not in state:
                    found = visit(nxt)
                    if found:
                        return found
            stack.pop()
            state[code] = 2
            return []

        for code in sorted(graph):
            if code not in state:
                found = visit(code)
                if found:
                    return found
        return []

    def open_subissues(self) -> list[SubIssue]:
        return [s for s in self.subissues if not s.status.is_done]

    @property
    def is_invalidated(self) -> bool:
        return self.status is IssueStatus.CLOSED and self.resolution in INVALIDATING_RESOLUTIONS

    # ------------------------------------------------------------ transitions
    def transition(
        self,
        target: IssueStatus,
        *,
        reason: str = "",
        resolution: Resolution | None = None,
        duplicate_of: IssueId | None = None,
    ) -> None:
        """Move the root through the state machine and enforce aggregate rules."""
        check_transition(self.status, target, resolution=resolution, reason=reason)
        if target is IssueStatus.RESOLVED or (
            target is IssueStatus.CLOSED and resolution in (None, Resolution.FIXED)
        ):
            pending = self.open_subissues()
            if pending:
                names = ", ".join(str(s.identifier) for s in pending)
                raise InvariantError(f"{self.identifier} cannot {target.value}: open sub-issues {names}")
        if target is IssueStatus.CLOSED and resolution is Resolution.DUPLICATE:
            if duplicate_of is None:
                raise InvariantError("closing as duplicate needs duplicate_of")
            if duplicate_of == self.identifier:
                raise InvariantError("an issue cannot duplicate itself")
            self.duplicate_of = duplicate_of
        previous = self.status
        self.status = target
        if target is IssueStatus.CLOSED:
            self.resolution = resolution or Resolution.FIXED
            if self.resolution in INVALIDATING_RESOLUTIONS | {Resolution.WONT_FIX}:
                self._cascade_close(self.resolution)
        if target is IssueStatus.REOPENED:
            self.resolution = None
        self.history.append((previous.value, target.value, reason))
        self.events.append(
            DomainEvent(
                "IssueStatusChanged",
                {"issue_id": str(self.identifier), "from": previous.value, "to": target.value, "reason": reason},
            )
        )

    def _cascade_close(self, resolution: Resolution) -> None:
        for sub in self.subissues:
            if not sub.status.is_done:
                sub.history.append((sub.status.value, IssueStatus.CLOSED.value, f"parent closed as {resolution}"))
                sub.status = IssueStatus.CLOSED
                sub.resolution = resolution

    def transition_subissue(
        self,
        code: str,
        target: IssueStatus,
        *,
        reason: str = "",
        resolution: Resolution | None = None,
    ) -> SubIssue:
        """Sub-issue transitions go through the root so the invariants hold.

        * no sub-issue change while the parent is closed (invalid/duplicate
          parents close their sub-issues themselves);
        * a sub-issue cannot resolve or close as fixed while a dependency is open;
        * reopening a sub-issue reopens a resolved parent (failed acceptance).
        """
        sub = self.subissue(code)
        if self.status is IssueStatus.CLOSED:
            state = "invalid" if self.is_invalidated else "closed"
            raise InvariantError(f"parent {self.identifier} is {state}; sub-issue {sub.identifier} cannot change")
        check_transition(sub.status, target, resolution=resolution, reason=reason)
        if target is IssueStatus.RESOLVED or (target is IssueStatus.CLOSED and resolution in (None, Resolution.FIXED)):
            waiting = [d for d in sub.depends_on if not self.subissue(d).status.is_done]
            if waiting:
                raise InvariantError(f"{sub.identifier} waits for {', '.join(waiting)}")
        previous = sub.status
        sub.status = target
        sub.resolution = (resolution or Resolution.FIXED) if target is IssueStatus.CLOSED else None
        sub.history.append((previous.value, target.value, reason))
        self.events.append(
            DomainEvent(
                "SubIssueStatusChanged",
                {"subissue_id": str(sub.identifier), "from": previous.value, "to": target.value, "reason": reason},
            )
        )
        if target is IssueStatus.REOPENED and self.status is IssueStatus.RESOLVED:
            self.transition(IssueStatus.REOPENED, reason=f"sub-issue {sub.code} reopened: {reason}")
        return sub

    # ------------------------------------------------------------ position
    def relative_position(self, directory: OrgDirectory) -> RelativePosition:
        """Where the issue sits in the hierarchy and where it escalates (Phase 6 routing)."""
        self.assert_nodes_exist(directory)
        owner = str(self.owning_node)
        involved = sorted({str(n) for n in self.nodes} | {str(n) for s in self.subissues for n in s.nodes})
        return position_for(directory, owner, involved, reserved=self.is_reserved_decision)

    def subissue_position(self, code: str, directory: OrgDirectory) -> RelativePosition:
        sub = self.subissue(code)
        owner = str(sub.owner_node or self.owning_node)
        involved = sorted({owner} | {str(n) for n in sub.nodes})
        return position_for(directory, owner, involved, reserved=sub.reserved_decision)

    # ------------------------------------------------------------ Phase 3 API
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


def position_for(directory: OrgDirectory, owner: str, involved: list[str], *, reserved: bool) -> RelativePosition:
    view = directory.node(owner)
    lca = directory.lowest_common_ancestor(involved)
    lca_view = directory.node(lca)
    if all(n == owner or owner in directory.node(n).path for n in involved):
        scope = IssueScope.LOCAL
    elif lca_view.layer >= 2:
        scope = IssueScope.CROSS_UNIT
    else:
        scope = IssueScope.CROSS_DEPUTY
    others = [n for n in involved if n != owner]
    route = directory.route(owner, others, reserved_decision=reserved)
    return RelativePosition(
        owner=owner,
        owner_layer=view.layer,
        owner_depth=view.depth,
        owner_path=view.path,
        involved=tuple(involved),
        common_ancestor=lca,
        common_ancestor_layer=lca_view.layer,
        scope=scope,
        escalation_action=route.action,
        escalation_target=route.target,
        reason=route.reason,
    )


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
