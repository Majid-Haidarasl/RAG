"""Phase 12 ACL: shipped issues and projects -> issue signals and sub-tasks."""

from dataclasses import dataclass

import pytest

from rag_core.prioritization.application.services import PrioritizationService, explain
from rag_core.prioritization.domain.scoring import PriorityScorer
from rag_core.prioritization.infrastructure.signals_acl import exposure_by_issue, issue_signals, sub_tasks
from rag_core.projects.infrastructure.registry_json import JsonProjectRegistry
from tests.fixtures.issues.seed import seed_issues
from tests.fixtures.projects.samples import PROJECTS_DIR, caps, shipped_like_signals, weights

pytestmark = [pytest.mark.prioritization]


@dataclass(frozen=True)
class _P:
    primary_issue: str
    remaining_mtoman: int | None


def test_exposure_counts_primary_issue_only() -> None:
    assert exposure_by_issue(JsonProjectRegistry(PROJECTS_DIR).load().projects) == {
        "AR-ISS-024": 1240, "AR-ISS-033": 410, "AR-ISS-031": 225}
    assert exposure_by_issue([_P("AR-ISS-024", 5), _P("AR-ISS-024", 9), _P("", 7), _P("AR-ISS-031", None)]) == {
        "AR-ISS-024": 9}


def test_signals_from_the_shipped_issues() -> None:
    exposure = exposure_by_issue(JsonProjectRegistry(PROJECTS_DIR).load().projects)
    sig = {s.issue_id: s for s in issue_signals(seed_issues(), {"AR-ISS-024": 4}, exposure)}
    main = sig["AR-ISS-024"]
    assert (main.priority, main.severity, main.urgency, main.risk, main.dependents) == ("P2", "high", 8, 8, 4)
    assert (main.exposure_mtoman, main.subissues, main.blocked_subissues, main.gaps) == (1240, 4, 2, 4)
    assert (main.affected_nodes, main.progress) == (7, 62)
    assert sig["AR-ISS-036"].duplicate_of == "AR-ISS-024" and not sig["AR-ISS-036"].is_open
    assert sig["AR-ISS-031"].exposure_mtoman == 225 and sig["AR-ISS-031"].progress is None


def test_shipped_signals_match_the_test_fixture() -> None:
    exposure = exposure_by_issue(JsonProjectRegistry(PROJECTS_DIR).load().projects)
    built = issue_signals(seed_issues(), {"AR-ISS-024": 4}, exposure)
    fixture = {s.issue_id: s for s in shipped_like_signals()}
    for s in built:
        f = fixture[s.issue_id]
        assert (s.priority, s.severity, s.urgency, s.risk, s.dependents, s.exposure_mtoman, s.gaps, s.status) == (
            f.priority, f.severity, f.urgency, f.risk, f.dependents, f.exposure_mtoman, f.gaps, f.status)


def test_sub_tasks_use_full_sibling_ids() -> None:
    tasks = sub_tasks(seed_issues())["AR-ISS-024"]
    assert [t.item_id for t in tasks] == ["AR-ISS-024/HW", "AR-ISS-024/WIN", "AR-ISS-024/WEB", "AR-ISS-024/LEG"]
    assert tasks[1].depends_on == ("AR-ISS-024/HW",) and tasks[1].status == "blocked"


def test_service_run_on_shipped_issues() -> None:
    exposure = exposure_by_issue(JsonProjectRegistry(PROJECTS_DIR).load().projects)
    signals = issue_signals(seed_issues(), {"AR-ISS-024": 4}, exposure)
    result = PrioritizationService(PriorityScorer(weights(), caps())).run(signals, sub_tasks(seed_issues()))
    assert result.ranking.key_ids == ["AR-ISS-024", "AR-ISS-031", "AR-ISS-035"]
    assert result.same_top1 and result.top_overlap(3) == 2
    assert [a.item_id for a in result.next_actions["AR-ISS-024"]] == ["AR-ISS-024/HW"]
    assert result.next_actions["AR-ISS-024"][0].unblocks == ("AR-ISS-024/LEG", "AR-ISS-024/WIN")
    data = result.to_dict()
    assert data["same_top1"] is True and data["sensitivity"]["perturbations"] == 18
    assert data["legacy_order"][:2] == ["AR-ISS-024", "AR-ISS-031"]


def test_explain_in_both_languages() -> None:
    top = PriorityScorer(weights(), caps()).rank(shipped_like_signals()).ranked[0]
    assert explain(top) == "urgency 12, risk 12, priority 11.25"
    assert explain(top, "fa", 2) == "فوریت 12, ریسک 12"
