"""Issue status categories and the validated transition state machine.

States (Phase 7): open → triaged → in_progress ⇄ blocked → resolved → closed,
with reopened for failed acceptance (AR-ISS-024 s.7: failed tests return to the
relevant sub-issue without deleting failure history).

Phase 3 status names stay readable as aliases so stored data and older tests
keep working: new→open, analysing / knowledge_identified / executor_identified
→ triaged, solution_proposed→in_progress, awaiting_decision / unresolved →
blocked, archived→closed.
"""

from __future__ import annotations

from enum import StrEnum

from rag_core.shared_kernel.errors import InvariantError


class IssueStatus(StrEnum):
    OPEN = "open"
    TRIAGED = "triaged"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    RESOLVED = "resolved"
    CLOSED = "closed"
    REOPENED = "reopened"

    # Phase 3 aliases (same members, old names)
    NEW = "open"
    ANALYSING = "triaged"
    KNOWLEDGE_IDENTIFIED = "triaged"
    EXECUTOR_IDENTIFIED = "triaged"
    SOLUTION_PROPOSED = "in_progress"
    AWAITING_DECISION = "blocked"
    UNRESOLVED = "blocked"
    ARCHIVED = "closed"

    @classmethod
    def _missing_(cls, value: object) -> IssueStatus | None:
        if isinstance(value, str):
            key = value.strip().lower()
            legacy = LEGACY_STATUS_VALUES.get(key)
            if legacy is not None:
                return cls(legacy)
            for member in cls:
                if member.value == key:
                    return member
        return None

    @property
    def category(self) -> StatusCategory:
        return _CATEGORY[self]

    @property
    def is_done(self) -> bool:
        return self in DONE_STATES


LEGACY_STATUS_VALUES = {
    "new": "open",
    "analysing": "triaged",
    "analyzing": "triaged",
    "knowledge_identified": "triaged",
    "executor_identified": "triaged",
    "solution_proposed": "in_progress",
    "awaiting_decision": "blocked",
    "unresolved": "blocked",
    "archived": "closed",
}


class StatusCategory(StrEnum):
    """Board-style grouping used in reports."""

    TODO = "todo"  # open, triaged, reopened
    ACTIVE = "active"  # in_progress
    WAITING = "waiting"  # blocked
    DONE = "done"  # resolved, closed


_CATEGORY = {
    IssueStatus.OPEN: StatusCategory.TODO,
    IssueStatus.TRIAGED: StatusCategory.TODO,
    IssueStatus.REOPENED: StatusCategory.TODO,
    IssueStatus.IN_PROGRESS: StatusCategory.ACTIVE,
    IssueStatus.BLOCKED: StatusCategory.WAITING,
    IssueStatus.RESOLVED: StatusCategory.DONE,
    IssueStatus.CLOSED: StatusCategory.DONE,
}

DONE_STATES = frozenset({IssueStatus.RESOLVED, IssueStatus.CLOSED})


class Resolution(StrEnum):
    FIXED = "fixed"
    DUPLICATE = "duplicate"
    INVALID = "invalid"
    WONT_FIX = "wont_fix"


# Closing an issue that was never worked on needs a non-fix resolution.
EARLY_CLOSE_RESOLUTIONS = frozenset({Resolution.DUPLICATE, Resolution.INVALID, Resolution.WONT_FIX})
INVALIDATING_RESOLUTIONS = frozenset({Resolution.DUPLICATE, Resolution.INVALID})

TRANSITIONS: dict[IssueStatus, frozenset[IssueStatus]] = {
    IssueStatus.OPEN: frozenset({IssueStatus.TRIAGED, IssueStatus.CLOSED}),
    IssueStatus.TRIAGED: frozenset({IssueStatus.IN_PROGRESS, IssueStatus.BLOCKED, IssueStatus.CLOSED}),
    IssueStatus.IN_PROGRESS: frozenset({IssueStatus.BLOCKED, IssueStatus.RESOLVED, IssueStatus.TRIAGED}),
    IssueStatus.BLOCKED: frozenset({IssueStatus.IN_PROGRESS, IssueStatus.TRIAGED}),
    IssueStatus.RESOLVED: frozenset({IssueStatus.CLOSED, IssueStatus.REOPENED}),
    IssueStatus.CLOSED: frozenset({IssueStatus.REOPENED}),
    IssueStatus.REOPENED: frozenset({IssueStatus.TRIAGED, IssueStatus.IN_PROGRESS}),
}


def can_transition(current: IssueStatus, target: IssueStatus) -> bool:
    return target in TRANSITIONS[current]


def check_transition(
    current: IssueStatus,
    target: IssueStatus,
    *,
    resolution: Resolution | None = None,
    reason: str = "",
) -> None:
    """Raise ``InvariantError`` unless ``current → target`` is allowed with its guards."""
    if not can_transition(current, target):
        allowed = ", ".join(sorted(s.value for s in TRANSITIONS[current]))
        raise InvariantError(f"transition {current} → {target} is not allowed (allowed: {allowed})")
    if target is IssueStatus.CLOSED:
        if current is IssueStatus.RESOLVED:
            if resolution not in (None, Resolution.FIXED):
                raise InvariantError("a resolved issue closes as fixed")
        elif resolution not in EARLY_CLOSE_RESOLUTIONS:
            raise InvariantError(f"closing from {current} needs resolution duplicate, invalid or wont_fix")
    if target in {IssueStatus.BLOCKED, IssueStatus.REOPENED} and not reason.strip():
        raise InvariantError(f"moving to {target} requires a reason")
