"""Issue aggregate metadata, sub-issues and closure invariants."""

from datetime import date

import pytest

from rag_core.issues.domain.model import (
    ContractRef,
    Issue,
    IssueCategory,
    SubIssue,
    approval_authority,
)
from rag_core.issues.domain.status import IssueStatus, Resolution
from rag_core.shared_kernel.errors import InvariantError, NotFoundError
from rag_core.shared_kernel.identifiers import DocumentId, IssueId, NodeIdentifier
from tests.fixtures.issues.seed import azarpakhsh, org_directory

pytestmark = [pytest.mark.issues, pytest.mark.issue_model]

N, I = NodeIdentifier, IssueId
S = IssueStatus


def _issue(**kw) -> Issue:
    return Issue.create(I("AR-ISS-050"), "Sample issue", N("N-SW"), **kw)


def _sub(code: str, pos: int, status=S.OPEN, depends=(), owner="N-SW-WEB") -> SubIssue:
    return SubIssue(
        I(f"AR-ISS-050/{code}"),
        f"Sub {code}",
        status,
        pos,
        owner_node=N(owner),
        depends_on=depends,
    )


def test_create_emits_event_and_keeps_metadata() -> None:
    issue = _issue(
        description="d",
        reporter_node=N("N-SW-SUP"),
        affected_nodes=(N("N-SW-WEB"), N("N-SW")),
        related_documents=(DocumentId("AR-SW-017"),),
        contract_ref=ContractRef("ar-cnt-1402-118"),
        category=IssueCategory.SOFTWARE,
        opened_on=date(2024, 8, 6),
        due_on=date(2024, 10, 11),
        tags=("Web", " web ", "API"),
    )
    assert issue.events[0].name == "IssueCreated"
    assert str(issue.contract_ref) == "AR-CNT-1402-118"
    assert issue.tags == ("api", "web")
    assert issue.nodes == (N("N-SW"), N("N-SW-WEB"))
    assert issue.status is S.OPEN


@pytest.mark.parametrize("bad", ["AR-CNT-118", "CNT-1402-118", "AR-CNT-1402-1180", ""])
def test_contract_reference_format(bad: str) -> None:
    with pytest.raises(InvariantError, match="contract"):
        ContractRef(bad)


def test_due_date_before_opening_is_rejected() -> None:
    with pytest.raises(InvariantError, match="due date"):
        _issue(opened_on=date(2024, 10, 1), due_on=date(2024, 9, 1))


def test_issue_cannot_link_to_itself() -> None:
    with pytest.raises(InvariantError, match="itself"):
        _issue(related_issues=(I("AR-ISS-050"),))
    with pytest.raises(InvariantError, match="itself"):
        _issue(duplicate_of=I("AR-ISS-050"))


def test_unknown_nodes_are_rejected_through_the_directory() -> None:
    with pytest.raises(NotFoundError, match="N-SW-AI"):
        _issue(affected_nodes=(N("N-SW-AI"),), directory=org_directory())


def test_known_nodes_pass_the_directory_check() -> None:
    _issue(
        affected_nodes=(N("N-SW-WEB"),),
        reporter_node=N("N-SW-SUP"),
        directory=org_directory(),
    )


@pytest.mark.parametrize(
    ("amount", "authority"),
    [
        (None, "unit"),
        (95, "unit"),
        (500, "unit"),
        (501, "ceo"),
        (2000, "ceo"),
        (2180, "board"),
    ],
)
def test_approval_authority_follows_ar_leg_009(amount, authority) -> None:
    assert approval_authority(amount) == authority


def test_reserved_decision_from_amount_or_flag() -> None:
    assert _issue(decision_amount_mtoman=2180).is_reserved_decision
    assert _issue(reserved_decision=True).is_reserved_decision
    assert not _issue(decision_amount_mtoman=95).is_reserved_decision


def test_subissue_dependency_on_unknown_sibling_is_rejected() -> None:
    issue = _issue()
    with pytest.raises(InvariantError, match="unknown sibling"):
        issue.add_subissue(_sub("WIN", 1, depends=("HW",)))


def test_subissue_cannot_depend_on_itself() -> None:
    with pytest.raises(InvariantError, match="itself"):
        _sub("HW", 1, depends=("HW",))


def test_dependency_cycle_is_rejected_and_rolled_back() -> None:
    issue = _issue()
    issue.add_subissue(_sub("A", 1))
    issue.subissues[0].depends_on = ("B",)  # simulate stored data pointing forward
    with pytest.raises(InvariantError, match="cycle"):
        issue.add_subissue(_sub("B", 2, depends=("A",)))
    assert [s.code for s in issue.subissues] == ["A"]


def test_dependency_cycle_detection_reports_the_path() -> None:
    issue = _issue()
    issue.subissues = [
        _sub("A", 1, depends=("C",)),
        _sub("B", 2, depends=("A",)),
        _sub("C", 3, depends=("B",)),
    ]
    cycle = issue.dependency_cycle()
    assert cycle[0] == cycle[-1] and set(cycle) == {"A", "B", "C"}


def test_closed_parent_accepts_no_new_subissues() -> None:
    issue = _issue()
    issue.transition(S.CLOSED, resolution=Resolution.INVALID)
    with pytest.raises(InvariantError, match="closed"):
        issue.add_subissue(_sub("HW", 1))


def test_parent_cannot_resolve_while_subissues_are_open() -> None:
    issue = azarpakhsh()
    with pytest.raises(InvariantError, match="open sub-issues"):
        issue.transition(S.RESOLVED)


def test_wont_fix_close_cascades_to_open_subissues() -> None:
    issue = _issue()
    issue.add_subissue(_sub("HW", 1))
    issue.add_subissue(_sub("WEB", 2, status=S.RESOLVED))
    issue.transition(S.TRIAGED)
    issue.transition(S.CLOSED, resolution=Resolution.WONT_FIX)
    assert issue.subissue("HW").resolution is Resolution.WONT_FIX
    assert issue.subissue("WEB").status is S.RESOLVED  # finished work keeps its state


def test_subissue_waits_for_its_dependency() -> None:
    issue = azarpakhsh()
    issue.transition_subissue("WIN", S.IN_PROGRESS)
    with pytest.raises(InvariantError, match="waits for HW"):
        issue.transition_subissue("WIN", S.RESOLVED)


def _resolve_all(issue: Issue) -> None:
    for code in ("HW", "WIN", "WEB", "LEG"):
        if issue.subissue(code).status is S.BLOCKED:
            issue.transition_subissue(code, S.IN_PROGRESS)
        issue.transition_subissue(code, S.RESOLVED)


def test_azarpakhsh_closes_only_after_all_three_evidence_paths() -> None:
    issue = azarpakhsh()
    _resolve_all(issue)
    issue.transition(S.RESOLVED)
    issue.transition(S.CLOSED)
    assert issue.status is S.CLOSED and issue.resolution is Resolution.FIXED
    assert issue.progress().value == 100


def test_resolving_one_subissue_does_not_close_the_parent() -> None:
    issue = azarpakhsh()
    issue.transition_subissue("HW", S.RESOLVED)
    assert issue.status is S.IN_PROGRESS
    assert issue.progress().value == 25


def test_failed_subissue_reopens_a_resolved_parent() -> None:
    issue = azarpakhsh()
    _resolve_all(issue)
    issue.transition(S.RESOLVED)
    issue.transition_subissue("WIN", S.REOPENED, reason="multi-station test failed")
    assert issue.status is S.REOPENED
    assert issue.history[-1][1] == "reopened"
    assert issue.subissue("WIN").history[-1] == (
        "resolved",
        "reopened",
        "multi-station test failed",
    )


def test_subissue_of_closed_parent_cannot_change() -> None:
    issue = azarpakhsh()
    _resolve_all(issue)
    issue.transition(S.RESOLVED)
    issue.transition(S.CLOSED)
    with pytest.raises(InvariantError, match="is closed"):
        issue.transition_subissue("WIN", S.REOPENED, reason="late failure")


def test_invalid_parent_closes_its_subissues_and_freezes_them() -> None:
    issue = _issue()
    issue.add_subissue(_sub("HW", 1))
    issue.add_subissue(_sub("WIN", 2, depends=("HW",)))
    issue.transition(S.CLOSED, resolution=Resolution.INVALID)
    assert issue.is_invalidated
    assert all(
        s.status is S.CLOSED and s.resolution is Resolution.INVALID
        for s in issue.subissues
    )
    with pytest.raises(InvariantError, match="is invalid"):
        issue.transition_subissue("HW", S.REOPENED, reason="x")


def test_duplicate_close_needs_target() -> None:
    issue = _issue()
    with pytest.raises(InvariantError, match="duplicate_of"):
        issue.transition(S.CLOSED, resolution=Resolution.DUPLICATE)
    issue.transition(
        S.CLOSED, resolution=Resolution.DUPLICATE, duplicate_of=I("AR-ISS-024")
    )
    assert issue.duplicate_of == I("AR-ISS-024")


def test_reopen_clears_resolution_and_records_history() -> None:
    issue = _issue()
    issue.transition(S.CLOSED, resolution=Resolution.WONT_FIX)
    issue.transition(S.REOPENED, reason="customer insists")
    assert issue.resolution is None
    assert [h[1] for h in issue.history] == ["closed", "reopened"]
    assert [e.name for e in issue.events].count("IssueStatusChanged") == 2


def test_subissue_lookup_by_code_or_id() -> None:
    issue = azarpakhsh()
    assert issue.subissue("WIN") is issue.subissue(I("AR-ISS-024/WIN"))
    with pytest.raises(NotFoundError):
        issue.subissue("AI")


def test_seeded_azarpakhsh_metadata() -> None:
    issue = azarpakhsh()
    assert str(issue.contract_ref) == "AR-CNT-1402-118"
    assert issue.category is IssueCategory.DELIVERY_DELAY
    assert DocumentId("AR-ISS-024") in issue.related_documents
    assert [s.code for s in issue.subissues] == ["HW", "WIN", "WEB", "LEG"]
    assert issue.subissue("LEG").reserved_decision
    assert issue.subissue("WIN").depends_on == ("HW",)
    assert issue.open_subissues() == issue.subissues
