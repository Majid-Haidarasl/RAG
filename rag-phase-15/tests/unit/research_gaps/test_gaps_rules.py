"""Phase 12 research-gap rules."""

import pytest

from rag_core.research_gaps.domain.model import Gap, GapKind, IssueStateView, Severity
from rag_core.research_gaps.domain.rules import (
    RULE_NAMES,
    RULE_ORDER,
    GapRuleBook,
    RuleSetting,
    blocked_dependency,
    knowledge_lack,
    missing_executor,
    research_open,
    scorecard_open,
    sort_gaps,
    stale_unsolved,
    unevidenced_record,
    unlinked_challenge,
)
from rag_core.shared_kernel.errors import InvariantError
from tests.fixtures.projects.samples import gap_inputs, rec_view, sub

pytestmark = [pytest.mark.research_gaps]

M = Severity.MEDIUM


def ids(gaps: list[Gap]) -> list[str]:
    return [g.gap_id for g in gaps]


def test_rule_table_is_complete() -> None:
    assert RULE_ORDER == ("RG", "KL", "EX", "DEP", "CH", "SC", "ST", "EV")
    assert (
        RULE_NAMES["KL"] == "knowledge_lack"
        and RULE_NAMES["DEP"] == "blocked_dependency"
    )


def test_research_open_fires_for_open_research_only() -> None:
    gaps = research_open(gap_inputs(), M)
    assert (
        ids(gaps) == ["RG:RES-PHOTO-TRIAGE"]
        and gaps[0].kind is GapKind.RESEARCH
        and gaps[0].severity is M
    )
    done = gap_inputs(records=(rec_view("RES-PHOTO-TRIAGE", "research", "recorded"),))
    assert research_open(done, M) == []


def test_research_linked_to_open_issue_is_more_severe() -> None:
    inputs = gap_inputs(
        records=(rec_view("RES-PHOTO-TRIAGE", "research", issues=("AR-ISS-024",)),)
    )
    assert research_open(inputs, M)[0].severity is Severity.HIGH


def test_knowledge_lack_is_high_when_blocked() -> None:
    gaps = {g.subject: g for g in knowledge_lack(gap_inputs(), M)}
    assert set(gaps) == {"AR-ISS-024/HW", "AR-ISS-024/WIN"}
    assert (
        gaps["AR-ISS-024/HW"].severity is M
        and gaps["AR-ISS-024/WIN"].severity is Severity.HIGH
    )
    assert gaps["AR-ISS-024/HW"].issue_id == "AR-ISS-024" and gaps[
        "AR-ISS-024/HW"
    ].documents == ("AR-HW-013",)
    assert (
        "AR-HW-013" in gaps["AR-ISS-024/HW"].title_en
        and "کمبود دانش" in gaps["AR-ISS-024/HW"].title_fa
    )


def test_closed_subissue_has_no_knowledge_gap() -> None:
    inputs = gap_inputs(
        subissues=(sub("AR-ISS-024/HW", "resolved", lacks=("AR-HW-013",)),)
    )
    assert knowledge_lack(inputs, M) == []


def test_missing_executor() -> None:
    inputs = gap_inputs(
        subissues=(
            sub("AR-ISS-024/WEB", lead="", executors=()),
            sub("AR-ISS-024/HW", lead=""),
            sub("AR-ISS-024/LEG", "closed", lead="", executors=()),
        )
    )
    assert ids(missing_executor(inputs, Severity.HIGH)) == ["EX:AR-ISS-024/WEB"]


def test_blocked_dependency_waits_for_unresolved_sibling() -> None:
    gaps = blocked_dependency(gap_inputs(), Severity.HIGH)
    assert (
        ids(gaps) == ["DEP:AR-ISS-024/WIN"]
        and gaps[0].detail == "waits_for=AR-ISS-024/HW"
    )
    resolved = gap_inputs(
        subissues=(
            sub("AR-ISS-024/HW", "resolved"),
            sub("AR-ISS-024/WIN", "blocked", depends_on=("AR-ISS-024/HW",)),
        )
    )
    assert blocked_dependency(resolved, Severity.HIGH) == []


def test_blocked_on_unknown_sibling_still_counts() -> None:
    inputs = gap_inputs(
        subissues=(sub("AR-ISS-024/WIN", "blocked", depends_on=("AR-ISS-024/XX",)),)
    )
    assert ids(blocked_dependency(inputs, Severity.HIGH)) == ["DEP:AR-ISS-024/WIN"]


def test_unlinked_challenge() -> None:
    assert ids(unlinked_challenge(gap_inputs(), M)) == ["CH:CHL-KEY-CAPACITY"]


def test_scorecard_open_and_conditional() -> None:
    gaps = {g.subject: g for g in scorecard_open(gap_inputs(), M)}
    assert set(gaps) == {"SC-CAP", "SC-RRQ"}
    assert gaps["SC-RRQ"].severity is M and gaps["SC-CAP"].severity is Severity.LOW
    assert gaps["SC-RRQ"].detail == "state=open; research=RES-RETRIEVAL-EVAL"


def test_stale_unsolved_when_all_issues_closed() -> None:
    inputs = gap_inputs(
        records=(
            rec_view("UNS-OLD", "unsolved_issue", issues=("AR-ISS-034",)),
            rec_view("UNS-AZP-DELAY", "unsolved_issue", issues=("AR-ISS-024",)),
        )
    )
    assert ids(stale_unsolved(inputs, Severity.LOW)) == ["ST:UNS-OLD"]


def test_unevidenced_record() -> None:
    inputs = gap_inputs(
        records=(rec_view("ACH-X", "achievement", "recorded", evidence=()),)
    )
    assert ids(unevidenced_record(inputs, Severity.HIGH)) == ["EV:ACH-X"]


def test_rulebook_detects_and_sorts() -> None:
    gaps = GapRuleBook().detect(gap_inputs())
    assert ids(gaps) == [
        "KL:AR-ISS-024/WIN",
        "DEP:AR-ISS-024/WIN",
        "RG:RES-PHOTO-TRIAGE",
        "KL:AR-ISS-024/HW",
        "CH:CHL-KEY-CAPACITY",
        "SC:SC-RRQ",
        "SC:SC-CAP",
    ]


def test_rulebook_settings_disable_and_change_severity() -> None:
    book = GapRuleBook(
        {"SC": RuleSetting(False, "medium"), "CH": RuleSetting(True, "high")}
    )
    gaps = book.detect(gap_inputs())
    assert not any(g.rule == "SC" for g in gaps)
    assert next(g for g in gaps if g.rule == "CH").severity is Severity.HIGH
    assert "SC" not in book.enabled


def test_rulebook_rejects_unknown_rules_and_severities() -> None:
    with pytest.raises(InvariantError):
        GapRuleBook({"ZZ": RuleSetting()})
    with pytest.raises(ValueError):
        RuleSetting(True, "extreme")


def test_gap_value_object() -> None:
    g = Gap("RG:X", "RG", "research", "medium", "X", "Title", "عنوان")
    assert g.kind is GapKind.RESEARCH and g.severity is M and g.title("fa") == "عنوان"
    assert g.to_dict()["kind"] == "research"
    with pytest.raises(InvariantError):
        Gap(" ", "RG", "research", "medium", "X", "t", "t")
    assert (
        sort_gaps([g, Gap("EV:Y", "EV", "evidence", "high", "Y", "t", "t")])[0].gap_id
        == "EV:Y"
    )
    assert IssueStateView("AR-ISS-034", "closed").active is False
