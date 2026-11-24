"""Status categories and the validated transition state machine."""

import pytest

from rag_core.issues.domain.status import (
    TRANSITIONS,
    IssueStatus,
    Resolution,
    StatusCategory,
    can_transition,
    check_transition,
)
from rag_core.shared_kernel.errors import InvariantError

pytestmark = [pytest.mark.issues, pytest.mark.issue_model]

S = IssueStatus
CANONICAL = [
    S.OPEN,
    S.TRIAGED,
    S.IN_PROGRESS,
    S.BLOCKED,
    S.RESOLVED,
    S.CLOSED,
    S.REOPENED,
]
ALLOWED = {
    (S.OPEN, S.TRIAGED),
    (S.OPEN, S.CLOSED),
    (S.TRIAGED, S.IN_PROGRESS),
    (S.TRIAGED, S.BLOCKED),
    (S.TRIAGED, S.CLOSED),
    (S.IN_PROGRESS, S.BLOCKED),
    (S.IN_PROGRESS, S.RESOLVED),
    (S.IN_PROGRESS, S.TRIAGED),
    (S.BLOCKED, S.IN_PROGRESS),
    (S.BLOCKED, S.TRIAGED),
    (S.RESOLVED, S.CLOSED),
    (S.RESOLVED, S.REOPENED),
    (S.CLOSED, S.REOPENED),
    (S.REOPENED, S.TRIAGED),
    (S.REOPENED, S.IN_PROGRESS),
}


def test_exactly_seven_canonical_states() -> None:
    assert list(IssueStatus) == CANONICAL
    assert set(TRANSITIONS) == set(CANONICAL)


@pytest.mark.parametrize("current", CANONICAL)
@pytest.mark.parametrize("target", CANONICAL)
def test_transition_matrix(current: IssueStatus, target: IssueStatus) -> None:
    assert can_transition(current, target) is ((current, target) in ALLOWED)


@pytest.mark.parametrize(
    ("current", "target"), sorted(ALLOWED - {(S.OPEN, S.CLOSED), (S.TRIAGED, S.CLOSED)})
)
def test_allowed_transitions_pass_with_their_guards(current, target) -> None:
    check_transition(current, target, reason="evidence recorded")


def test_disallowed_transition_names_the_allowed_targets() -> None:
    with pytest.raises(InvariantError, match="allowed: closed, triaged"):
        check_transition(S.OPEN, S.RESOLVED)


@pytest.mark.parametrize(
    "resolution", [Resolution.DUPLICATE, Resolution.INVALID, Resolution.WONT_FIX]
)
def test_early_close_needs_a_non_fix_resolution(resolution) -> None:
    check_transition(S.OPEN, S.CLOSED, resolution=resolution)
    check_transition(S.TRIAGED, S.CLOSED, resolution=resolution)


@pytest.mark.parametrize("resolution", [None, Resolution.FIXED])
def test_early_close_without_reason_is_rejected(resolution) -> None:
    with pytest.raises(InvariantError, match="duplicate, invalid or wont_fix"):
        check_transition(S.OPEN, S.CLOSED, resolution=resolution)


def test_resolved_issue_closes_only_as_fixed() -> None:
    check_transition(S.RESOLVED, S.CLOSED)
    check_transition(S.RESOLVED, S.CLOSED, resolution=Resolution.FIXED)
    with pytest.raises(InvariantError, match="fixed"):
        check_transition(S.RESOLVED, S.CLOSED, resolution=Resolution.INVALID)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (S.TRIAGED, S.BLOCKED),
        (S.IN_PROGRESS, S.BLOCKED),
        (S.CLOSED, S.REOPENED),
        (S.RESOLVED, S.REOPENED),
    ],
)
def test_blocking_and_reopening_need_a_reason(current, target) -> None:
    with pytest.raises(InvariantError, match="reason"):
        check_transition(current, target, reason="  ")


@pytest.mark.parametrize(
    ("legacy", "canonical"),
    [
        ("new", S.OPEN),
        ("analysing", S.TRIAGED),
        ("knowledge_identified", S.TRIAGED),
        ("executor_identified", S.TRIAGED),
        ("solution_proposed", S.IN_PROGRESS),
        ("awaiting_decision", S.BLOCKED),
        ("unresolved", S.BLOCKED),
        ("archived", S.CLOSED),
        ("IN_PROGRESS", S.IN_PROGRESS),
    ],
)
def test_phase3_status_names_map_to_canonical_states(
    legacy: str, canonical: IssueStatus
) -> None:
    assert IssueStatus(legacy) is canonical


def test_phase3_member_aliases() -> None:
    assert (
        S.NEW is S.OPEN and S.AWAITING_DECISION is S.BLOCKED and S.ARCHIVED is S.CLOSED
    )


def test_unknown_status_is_rejected() -> None:
    with pytest.raises(ValueError):
        IssueStatus("done-ish")


@pytest.mark.parametrize(
    ("status", "category"),
    [
        (S.OPEN, StatusCategory.TODO),
        (S.TRIAGED, StatusCategory.TODO),
        (S.REOPENED, StatusCategory.TODO),
        (S.IN_PROGRESS, StatusCategory.ACTIVE),
        (S.BLOCKED, StatusCategory.WAITING),
        (S.RESOLVED, StatusCategory.DONE),
        (S.CLOSED, StatusCategory.DONE),
    ],
)
def test_status_categories(status, category) -> None:
    assert status.category is category
    assert status.is_done is (category is StatusCategory.DONE)
