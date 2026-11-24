"""Rule-based decomposition into sub-issues per cause path / affected unit."""

import pytest

from rag_core.issues.application.services import IssueService
from rag_core.issues.domain.decomposition import (
    ARMANRAYAN_RULES,
    CausePathRule,
    RuleBasedDecomposer,
    SubIssueDraft,
)
from rag_core.issues.domain.model import Issue
from rag_core.issues.domain.status import IssueStatus, Resolution
from rag_core.issues.infrastructure.memory import InMemoryIssueRepository
from rag_core.shared_kernel.errors import InvariantError, NotFoundError
from rag_core.shared_kernel.identifiers import IssueId, NodeIdentifier
from tests.fixtures.issues.seed import azarpakhsh, org_directory

pytestmark = [pytest.mark.issues, pytest.mark.issue_model]

N = NodeIdentifier


def _fresh_azarpakhsh() -> Issue:
    issue = azarpakhsh()
    issue.subissues = []
    return issue


def _issue(
    title: str, description: str = "", owner: str = "N-SW-SUP", affected=()
) -> Issue:
    return Issue.create(
        IssueId("AR-ISS-080"),
        title,
        N(owner),
        description=description,
        affected_nodes=tuple(N(a) for a in affected),
    )


def test_azarpakhsh_produces_the_four_cause_paths() -> None:
    drafts = RuleBasedDecomposer(directory=org_directory()).decompose(
        _fresh_azarpakhsh()
    )
    assert [(d.code, d.owner_node) for d in drafts] == [
        ("HW", "N-HW-REP"),
        ("WIN", "N-SW-WIN"),
        ("WEB", "N-SW-WEB"),
        ("LEG", "N-ADM-LEG"),
    ]


def test_azarpakhsh_drafts_match_the_seeded_subissues() -> None:
    seeded = azarpakhsh()
    drafts = {d.code: d for d in RuleBasedDecomposer().decompose(_fresh_azarpakhsh())}
    for sub in seeded.subissues:
        d = drafts[sub.code]
        assert d.owner_node == str(sub.owner_node)
        assert d.depends_on == sub.depends_on
        assert d.reserved_decision is sub.reserved_decision


def test_hardware_path_covers_controller_and_ram_with_supporting_teams() -> None:
    hw = RuleBasedDecomposer().decompose(_fresh_azarpakhsh())[0]
    assert {"raid", "controller", "ram"} <= set(hw.matched)
    assert hw.supporting_nodes == ("N-HW-ADV", "N-HW-ASM")
    assert "AR-HW-015" in hw.related_documents


def test_apply_adds_ordered_subissues_with_dependencies() -> None:
    issue = _fresh_azarpakhsh()
    added = RuleBasedDecomposer(directory=org_directory()).apply(issue)
    assert [s.position for s in added] == [1, 2, 3, 4]
    assert all(s.status is IssueStatus.OPEN for s in added)
    assert issue.subissue("WIN").depends_on == ("HW",)
    assert issue.subissue("LEG").depends_on == ("HW",)
    assert issue.subissue("WEB").depends_on == ()
    assert [e.name for e in issue.events].count("IssueDecomposed") == 4


def test_apply_is_idempotent() -> None:
    issue = _fresh_azarpakhsh()
    decomposer = RuleBasedDecomposer()
    decomposer.apply(issue)
    assert decomposer.apply(issue) == []
    assert len(issue.subissues) == 4


def test_apply_on_seeded_issue_adds_nothing() -> None:
    issue = azarpakhsh()
    assert RuleBasedDecomposer().apply(issue) == []


def test_persian_only_text_decomposes_the_same_way() -> None:
    issue = _issue(
        "ناهماهنگی کنترلر RAID و حافظه سرور با کلاینت ویندوزی",
        "تأخیر ماژول گزارش‌گیری وب و تأخیر تحویل قرارداد",
    )
    assert [d.code for d in RuleBasedDecomposer().decompose(issue)] == [
        "HW",
        "WIN",
        "WEB",
        "LEG",
    ]


@pytest.mark.parametrize(
    ("text", "codes"),
    [
        ("RAID controller firmware is unstable", ["HW"]),
        ("Windows driver fails on the desktop client", ["WIN"]),
        ("The web reporting dashboard is late", ["WEB"]),
        ("Delay penalty under the contract amendment", ["LEG"]),
        ("Invoice and receivable dispute", ["FIN"]),
        ("Flutter mobile build is late", ["MOB"]),
        ("Complete outage breaches the SLA", ["SUP"]),
        ("Wireframe usability review", ["UX"]),
    ],
)
def test_single_cause_paths(text: str, codes: list[str]) -> None:
    assert [
        d.code
        for d in RuleBasedDecomposer(per_unit_fallback=False).decompose(_issue(text))
    ] == codes


def test_generic_server_problem_is_not_a_hardware_trigger() -> None:
    assert (
        RuleBasedDecomposer(per_unit_fallback=False).decompose(
            _issue("Vague server problem at the customer")
        )
        == []
    )


def test_dependencies_are_dropped_when_the_path_is_absent() -> None:
    drafts = RuleBasedDecomposer().decompose(_issue("Windows driver version mismatch"))
    assert drafts[0].code == "WIN" and drafts[0].depends_on == ()


def test_per_unit_fallback_for_uncovered_affected_nodes() -> None:
    issue = _issue(
        "Windows driver mismatch", owner="N-SW-WIN", affected=("N-ADM-SEC", "N-SW-WIN")
    )
    drafts = RuleBasedDecomposer().decompose(issue)
    assert [d.code for d in drafts] == ["WIN", "UADMSEC"]
    assert drafts[1].owner_node == "N-ADM-SEC" and drafts[1].rule == "per_unit"


def test_owner_missing_from_registry_is_rejected() -> None:
    rules = (CausePathRule("AI", "AI team", "تیم هوش مصنوعی", "N-SW-AI", ("model",)),)
    with pytest.raises(NotFoundError, match="N-SW-AI"):
        RuleBasedDecomposer(rules=rules, directory=org_directory()).decompose(
            _issue("model drift")
        )


def test_every_default_rule_owner_exists_in_the_registry() -> None:
    org = org_directory()
    for rule in ARMANRAYAN_RULES:
        assert org.exists(rule.owner_node), rule.code
        assert all(org.exists(n) for n in rule.supporting_nodes), rule.code


def test_no_match_and_no_affected_nodes_gives_no_drafts() -> None:
    issue = _issue("Coffee machine broken")
    assert RuleBasedDecomposer().decompose(issue) == []
    assert RuleBasedDecomposer().apply(issue) == []


def test_closed_parent_cannot_be_decomposed() -> None:
    issue = _issue("RAID controller fails")
    issue.transition(IssueStatus.CLOSED, resolution=Resolution.INVALID)
    with pytest.raises(InvariantError, match="closed"):
        RuleBasedDecomposer().apply(issue)


class StubLlmDecomposer:
    """Implements the optional IssueDecomposer port; no model is called."""

    def decompose(self, issue: Issue) -> list[SubIssueDraft]:
        return [
            SubIssueDraft(
                "UX",
                "Report readability",
                "خوانایی گزارش",
                "N-SW-UX",
                (),
                (),
                (),
                False,
                ("stub",),
            )
        ]


def test_service_accepts_an_alternative_decomposer_port() -> None:
    service = IssueService(
        InMemoryIssueRepository(), org_directory(), decomposer=StubLlmDecomposer()
    )
    issue = _issue("anything")
    added = service.decompose(issue)
    assert [s.code for s in added] == ["UX"] and str(added[0].owner_node) == "N-SW-UX"
