"""Phase 12 project tracking model: projects, records, scorecard and the registry."""

import pytest

from rag_core.projects.domain.model import (
    RECORD_KINDS,
    ClaimState,
    ProjectStatus,
    RecordKind,
    ScorecardDimension,
)
from rag_core.shared_kernel.errors import InvariantError
from tests.fixtures.projects.samples import project, record, registry

pytestmark = [pytest.mark.projects]


def test_project_normalizes_status_and_lists_all_nodes() -> None:
    p = project()
    assert p.status is ProjectStatus.AT_RISK
    assert p.all_nodes == ("N-CEO", "N-HW-REP", "N-SW-WEB")


def test_project_numbers_skip_unknown_values() -> None:
    assert project().numbers() == {"progress_percent": 62, "remaining_mtoman": 1240, "contract_value_mtoman": 2180}
    assert project(contract_value_mtoman=None).numbers() == {"progress_percent": 62, "remaining_mtoman": 1240}


@pytest.mark.parametrize("progress", [-1, 101])
def test_progress_must_be_a_percentage(progress: int) -> None:
    with pytest.raises(InvariantError):
        project(progress_percent=progress)


def test_remaining_cannot_exceed_contract_value() -> None:
    with pytest.raises(InvariantError, match="larger than the contract"):
        project(remaining_mtoman=2500)


def test_negative_amount_is_rejected() -> None:
    with pytest.raises(InvariantError, match="negative"):
        project(remaining_mtoman=-5)


def test_primary_issue_must_be_linked() -> None:
    with pytest.raises(InvariantError, match="primary issue"):
        project(primary_issue="AR-ISS-031")


def test_completed_project_needs_full_progress() -> None:
    with pytest.raises(InvariantError, match="100%"):
        project(status="completed")
    assert project(status="completed", progress_percent=100, remaining_mtoman=0).status is ProjectStatus.COMPLETED


def test_project_needs_both_names_and_a_valid_code() -> None:
    with pytest.raises(InvariantError):
        project(name_fa=" ")
    with pytest.raises(InvariantError):
        project(project_id="AZP-118")


def test_record_converts_kind_and_state() -> None:
    r = record("RES-PHOTO-TRIAGE", "research")
    assert r.kind is RecordKind.RESEARCH and r.state is ClaimState.OPEN
    assert not r.is_lesson and record().is_lesson and record("CHL-X", "challenge").is_lesson


def test_record_text_by_language() -> None:
    r = record()
    assert r.statement("fa").startswith("این چرخه") and r.statement("en").startswith("The cycle")
    assert r.title("fa") == "مسیر صریح" and r.title("en") == "Explicit path"


def test_unknown_record_kind_is_rejected() -> None:
    with pytest.raises(ValueError):
        record("X-1", "rumour")


def test_registry_lookups_and_counts() -> None:
    reg = registry(record(), record("RES-PHOTO-TRIAGE", "research"), record("UNS-AZP-DELAY", "unsolved_issue",
                                                                            project="PRJ-AZP-118"))
    assert reg.counts_by_kind() == {"research": 1, "achievement": 1, "challenge": 0, "unsolved_issue": 1}
    assert tuple(RECORD_KINDS) == ("research", "achievement", "challenge", "unsolved_issue")
    assert reg.record("RES-PHOTO-TRIAGE") is not None and reg.record("NOPE") is None
    assert reg.project("PRJ-AZP-118") is not None
    assert [r.record_id for r in reg.records_of("unsolved_issue", "PRJ-AZP-118")] == ["UNS-AZP-DELAY"]
    assert [p.project_id for p in reg.project_of_issue("AR-ISS-024")] == ["PRJ-AZP-118"]


def test_scorecard_dimension_state() -> None:
    d = ScorecardDimension("SC-RRQ", "Repair retrieval quality", "کیفیت بازیابی تعمیر", "open")
    assert d.state is ClaimState.OPEN
    with pytest.raises(InvariantError):
        ScorecardDimension(" ", "x", "y", "open")
