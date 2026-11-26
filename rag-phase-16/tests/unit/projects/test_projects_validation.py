"""Phase 12 registry validation: references, record rules and project health."""

import pytest

from rag_core.projects.domain.validation import IssueFacts, RegistryValidator, health
from tests.fixtures.projects.samples import (
    DOCS,
    ISSUES,
    NODES,
    project,
    record,
    registry,
)

pytestmark = [pytest.mark.projects]


def validator() -> RegistryValidator:
    return RegistryValidator(NODES, DOCS, ISSUES)


def codes(reg) -> list[str]:
    return [p.code for p in validator().validate(reg)]


def test_clean_registry_has_no_problems() -> None:
    reg = registry(
        record(),
        record("RES-PHOTO-TRIAGE", "research"),
        record("UNS-AZP-DELAY", "unsolved_issue"),
    )
    assert validator().validate(reg) == []


def test_unknown_references_are_reported() -> None:
    reg = registry(
        record(
            nodes=("N-XXX",),
            evidence=("AR-XYZ-999",),
            issues=("AR-ISS-099",),
            project="PRJ-NONE",
        )
    )
    assert codes(reg) == [
        "unknown_node",
        "unknown_document",
        "unknown_issue",
        "unknown_project",
    ]


def test_duplicate_ids_across_the_registry() -> None:
    assert "duplicate_id" in codes(registry(record(), record()))


def test_record_without_evidence() -> None:
    assert "missing_evidence" in codes(registry(record(evidence=())))


def test_lesson_needs_conditions_but_unsolved_issue_does_not() -> None:
    assert codes(registry(record(conditions=" "))) == ["missing_conditions"]
    assert (
        codes(registry(record("UNS-AZP-DELAY", "unsolved_issue", conditions=""))) == []
    )


def test_achievement_cannot_be_open() -> None:
    assert codes(registry(record(state="open"))) == ["achievement_open"]


def test_research_may_not_claim_a_result() -> None:
    assert codes(
        registry(record("RES-PHOTO-TRIAGE", "research", validated_result=True))
    ) == ["research_claims_result"]
    assert codes(
        registry(record("RES-PHOTO-TRIAGE", "research", state="recorded"))
    ) == ["research_claims_result"]


def test_research_plan_must_be_complete() -> None:
    assert codes(registry(record("RES-PHOTO-TRIAGE", "research", risks=()))) == [
        "research_plan_incomplete"
    ]


def test_unsolved_issue_rules() -> None:
    assert codes(registry(record("UNS-AZP-DELAY", "unsolved_issue", issues=()))) == [
        "unsolved_needs_issue"
    ]
    assert codes(
        registry(record("UNS-AZP-DELAY", "unsolved_issue", state="conditional"))
    ) == ["unsolved_not_open"]


def test_project_status_must_match_linked_issues() -> None:
    reg = registry(projects=(project(status="active"),))
    assert codes(reg) == ["status_inconsistent"]


def test_project_references_are_checked() -> None:
    reg = registry(projects=(project(owner_node="N-XXX", evidence=()),))
    assert codes(reg) == ["unknown_node", "missing_evidence"]


def test_health_levels() -> None:
    assert health([ISSUES["AR-ISS-024"]]) == "at_risk"
    assert health([ISSUES["AR-ISS-031"]]) == "watch"
    assert health([ISSUES["AR-ISS-034"]]) == "on_track"
    assert health([]) == "on_track"
    assert (
        health([IssueFacts("AR-ISS-031", "triaged", 5, 1)]) == "at_risk"
    )  # a blocked sub-issue
    assert health([ISSUES["AR-ISS-031"]], risk_threshold=5) == "at_risk"


def test_problem_text() -> None:
    p = validator().validate(registry(record(evidence=("AR-XYZ-999",))))[0]
    assert str(p) == "unknown_document:ACH-IKE-PATH"
