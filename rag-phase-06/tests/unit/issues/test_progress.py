import pytest
from decimal import Decimal

from rag_core.issues.domain.model import (
    Issue,
    IssueStatus,
    ProgressPercentage,
    PriorityScore,
    SubIssue,
    rank_issues,
)
from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.identifiers import IssueId, NodeIdentifier

pytestmark = pytest.mark.issues


def test_issue_without_title_is_rejected() -> None:
    with pytest.raises(InvariantError, match="title"):
        Issue.create(IssueId("AR-ISS-024"), "  ", NodeIdentifier("N-LIB"))


def test_subissue_win_has_parent_and_position_two() -> None:
    issue = Issue.create(
        IssueId("AR-ISS-024"),
        "Azarpakhsh warehouse delivery delay",
        NodeIdentifier("N-LIB"),
    )
    issue.add_subissue(SubIssue(IssueId("AR-ISS-024/HW"), "Hardware mismatch", IssueStatus.IN_PROGRESS, 1))
    issue.add_subissue(SubIssue(IssueId("AR-ISS-024/WIN"), "Windows client", IssueStatus.IN_PROGRESS, 2))
    issue.add_subissue(SubIssue(IssueId("AR-ISS-024/LEG"), "Legal amendment", IssueStatus.AWAITING_DECISION, 3))
    win = issue.subissue(IssueId("AR-ISS-024/WIN"))
    assert win.identifier.parent_id == IssueId("AR-ISS-024")
    assert win.position == 2


def test_issue_progress_all_subissues_resolved_returns_100() -> None:
    issue = Issue.create(IssueId("AR-ISS-024"), "Azarpakhsh", NodeIdentifier("N-LIB"))
    issue.add_subissue(SubIssue(IssueId("AR-ISS-024/HW"), "HW", IssueStatus.RESOLVED, 1))
    issue.add_subissue(SubIssue(IssueId("AR-ISS-024/WIN"), "WIN", IssueStatus.RESOLVED, 2))
    assert issue.progress() == ProgressPercentage.from_int(100)


def test_progress_is_mean_of_subissues_and_stays_in_range() -> None:
    issue = Issue.create(IssueId("AR-ISS-024"), "Azarpakhsh", NodeIdentifier("N-LIB"))
    issue.add_subissue(
        SubIssue(IssueId("AR-ISS-024/HW"), "HW", IssueStatus.IN_PROGRESS, 1, ProgressPercentage.from_int(80))
    )
    issue.add_subissue(
        SubIssue(IssueId("AR-ISS-024/WIN"), "WIN", IssueStatus.IN_PROGRESS, 2, ProgressPercentage.from_int(40))
    )
    assert issue.progress().value == Decimal("60.00")
    with pytest.raises(InvariantError):
        ProgressPercentage.from_int(101)


def test_priority_ranking_is_stable_for_identical_input() -> None:
    a = Issue.create(IssueId("AR-ISS-001"), "A", NodeIdentifier("N-SW"), urgency=5, risk=5, dependents=2)
    b = Issue.create(IssueId("AR-ISS-002"), "B", NodeIdentifier("N-SW"), urgency=5, risk=5, dependents=2)
    c = Issue.create(IssueId("AR-ISS-003"), "C", NodeIdentifier("N-SW"), urgency=9, risk=5, dependents=2)
    first = [i.identifier for i in rank_issues([b, c, a])]
    second = [i.identifier for i in rank_issues([a, b, c])]
    assert first == second
    assert first[0] == IssueId("AR-ISS-003")
    # Identical scores keep IssueId order.
    assert first[1:] == [IssueId("AR-ISS-001"), IssueId("AR-ISS-002")]
    assert a.priority() == PriorityScore(Decimal(3 * 5 + 2 * 5 + 2))


def test_subissue_with_wrong_parent_is_rejected() -> None:
    issue = Issue.create(IssueId("AR-ISS-024"), "Azarpakhsh", NodeIdentifier("N-LIB"))
    with pytest.raises(InvariantError, match="does not belong"):
        issue.add_subissue(SubIssue(IssueId("AR-ISS-099/HW"), "x", IssueStatus.NEW, 1))
