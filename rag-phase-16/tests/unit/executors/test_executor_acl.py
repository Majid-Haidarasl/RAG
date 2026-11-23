"""ACLs of the executors context: Phase 6 hierarchy and Phase 7 issues."""

import pytest

from rag_core.executors.infrastructure.issues_acl import request_for_issue, request_for_subissue
from rag_core.shared_kernel.errors import NotFoundError
from tests.fixtures.executors.registry import team_directory
from tests.fixtures.issues.seed import azarpakhsh

pytestmark = [pytest.mark.executors, pytest.mark.matching]


def test_team_directory_reads_the_phase6_registry() -> None:
    teams = team_directory()
    assert teams.exists("N-SW-WIN")
    view = teams.team("N-SW-WIN")
    assert view.layer == 3 and view.parent_id == "N-SW" and "ویندوز" in view.name_fa
    assert teams.team("N-LIB").layer == 4


def test_team_directory_rejects_unknown_or_malformed_nodes() -> None:
    teams = team_directory()
    assert not teams.exists("N-NOPE")
    assert not teams.exists("not-a-node")
    with pytest.raises(NotFoundError):
        teams.team("N-NOPE")


def test_subissue_request_carries_nodes_documents_and_decision() -> None:
    leg = azarpakhsh().subissue("LEG")
    req = request_for_subissue(leg)
    assert req.item_id == "AR-ISS-024/LEG" and req.owner_node == "N-ADM-LEG"
    assert req.supporting_nodes == ("N-ADM-FIN",)
    assert req.related_documents == ("AR-LEG-009", "AR-FIN-010")
    assert req.reserved_decision and req.named_executors == ("Mahsa Jalali", "Reza Abbasi")
    assert "penalty" in req.text and "amendment" in req.text


def test_issue_request_uses_affected_nodes_and_skips_its_own_file() -> None:
    issue = azarpakhsh()
    req = request_for_issue(issue)
    assert req.item_id == "AR-ISS-024" and req.owner_node == "N-LIB"
    assert "N-HW-REP" in req.supporting_nodes and "N-LIB" not in req.supporting_nodes
    assert "AR-ISS-024" not in req.related_documents and "AR-EXE-023" in req.related_documents
