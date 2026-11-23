"""Phase 12 gap service and report."""

import pytest

from rag_core.research_gaps.application.services import GapReport, GapService
from rag_core.research_gaps.domain.model import Gap
from tests.fixtures.projects.samples import gap_inputs

pytestmark = [pytest.mark.research_gaps]


def report() -> GapReport:
    return GapService().detect(gap_inputs())


def test_counts_by_rule_severity_and_kind() -> None:
    r = report()
    assert r.by_rule() == {"RG": 1, "KL": 2, "DEP": 1, "CH": 1, "SC": 2}
    assert r.by_severity() == {"high": 2, "medium": 4, "low": 1}
    assert r.by_kind() == {"knowledge": 2, "dependency": 1, "research": 1, "challenge": 1, "measurement": 2}


def test_gaps_per_issue() -> None:
    r = report()
    assert r.count_by_issue() == {"AR-ISS-024": 3}
    assert [g.gap_id for g in r.for_issue("AR-ISS-024")] == ["KL:AR-ISS-024/WIN", "DEP:AR-ISS-024/WIN",
                                                             "KL:AR-ISS-024/HW"]
    assert r.for_issue("AR-ISS-031") == []


def test_issue_id_is_inferred_from_subject() -> None:
    r = GapReport([Gap("X:AR-ISS-031/UI", "KL", "knowledge", "low", "AR-ISS-031/UI", "t", "t")])
    assert r.count_by_issue() == {"AR-ISS-031": 1}


def test_report_to_dict() -> None:
    data = report().to_dict()
    assert data["total"] == 7 and len(data["gaps"]) == 7
    assert data["gaps"][0]["gap_id"] == "KL:AR-ISS-024/WIN"


def test_empty_report() -> None:
    r = GapReport()
    assert r.by_rule() == {} and r.by_severity() == {"high": 0, "medium": 0, "low": 0} and r.count_by_issue() == {}
