"""Phase 12 project tracking service: overview, matrix and totals."""

import pytest

from rag_core.projects.application.services import ProjectTrackingService
from rag_core.projects.infrastructure.issues_acl import issue_facts
from rag_core.projects.infrastructure.registry_json import JsonProjectRegistry
from tests.fixtures.issues.seed import seed_issues
from tests.fixtures.projects.samples import ISSUES, PROJECTS_DIR, project, record, registry

pytestmark = [pytest.mark.projects]


def shipped_service() -> ProjectTrackingService:
    return ProjectTrackingService(JsonProjectRegistry(PROJECTS_DIR).load(), issue_facts(seed_issues()))


def test_overview_of_the_shipped_projects() -> None:
    rows = {o.project_id: o for o in shipped_service().overview()}
    azp = rows["PRJ-AZP-118"]
    assert (azp.health, azp.issues, azp.open_issues, azp.blocked_subissues) == ("at_risk", 4, 3, 2)
    assert azp.records == {"research": 0, "achievement": 1, "challenge": 1, "unsolved_issue": 3}
    assert (rows["PRJ-RHS-PORTAL"].health, rows["PRJ-RHS-PORTAL"].open_issues) == ("watch", 1)
    assert rows["PRJ-DSP-VISITOR"].health == "watch"


def test_matrix_groups_cycle_level_records() -> None:
    m = shipped_service().matrix()
    assert m["cycle"] == {"research": 2, "achievement": 2, "challenge": 3, "unsolved_issue": 0}
    assert m["PRJ-DSP-VISITOR"] == {"research": 0, "achievement": 1, "challenge": 0, "unsolved_issue": 1}


def test_open_research_and_remaining_total() -> None:
    s = shipped_service()
    assert s.open_research() == ["RES-PHOTO-TRIAGE", "RES-RETRIEVAL-EVAL"]
    assert s.remaining_total() == 1240 + 410 + 225


def test_overview_row_to_dict() -> None:
    row = ProjectTrackingService(registry(record()), ISSUES).overview()[0]
    data = row.to_dict()
    assert data["project_id"] == "PRJ-AZP-118" and data["health"] == "at_risk"
    assert data["records"]["achievement"] == 0   # the sample record has no project


def test_unknown_linked_issue_is_ignored_in_overview() -> None:
    reg = registry(projects=(project(issues=("AR-ISS-024", "AR-ISS-099")),))
    row = ProjectTrackingService(reg, ISSUES).overview()[0]
    assert row.issues == 2 and row.open_issues == 1
