"""Relative position through the hierarchy ACL (Phase 6 registry and escalation)."""

import pytest

from rag_core.hierarchy.application.workflows import HierarchyWorkflowService, load_and_validate
from rag_core.issues.domain.model import Issue, IssueScope
from rag_core.issues.infrastructure.hierarchy_acl import HierarchyOrgDirectory
from rag_core.shared_kernel.errors import NotFoundError
from rag_core.shared_kernel.identifiers import IssueId, NodeIdentifier
from tests.fixtures.issues.seed import REGISTRY_DIR, azarpakhsh, org_directory, seed_issues

pytestmark = [pytest.mark.issues, pytest.mark.issue_model]

N = NodeIdentifier


def test_acl_translates_nodes() -> None:
    org = org_directory()
    view = org.node("N-SW-WIN")
    assert (view.layer, view.depth) == (3, 3)
    assert view.path == ("N-BRD", "N-CEO", "N-SW", "N-SW-WIN")
    assert org.exists("N-LIB") and not org.exists("N-SW-AI") and not org.exists("bad id")
    with pytest.raises(NotFoundError):
        org.node("N-SW-AI")


def test_acl_reuses_phase6_escalation() -> None:
    org = org_directory()
    assert org.route("N-SW-WEB", ["N-SW-MOB"]).target == "N-SW"
    assert org.route("N-SW-WEB", ["N-HW-REP"]).target == "N-CEO"
    assert org.route("N-SW-WEB", [], reserved_decision=True).target == "N-BRD"
    assert org.route("N-SW", ["N-SW-WEB"]).action == "answer"
    assert org.lowest_common_ancestor(["N-HW-REP", "N-HW-ASM"]) == "N-HW"


@pytest.mark.parametrize(
    ("issue_id", "layer", "depth", "scope", "target"),
    [
        ("AR-ISS-024", 4, 2, IssueScope.CROSS_DEPUTY, "N-CEO"),
        ("AR-ISS-031", 3, 3, IssueScope.CROSS_UNIT, "N-SW"),
        ("AR-ISS-032", 3, 3, IssueScope.CROSS_UNIT, "N-ADM"),
        ("AR-ISS-033", 3, 3, IssueScope.CROSS_UNIT, "N-SW"),
        ("AR-ISS-034", 3, 3, IssueScope.CROSS_UNIT, "N-HW"),
        ("AR-ISS-035", 2, 2, IssueScope.CROSS_DEPUTY, "N-CEO"),
        ("AR-ISS-036", 3, 3, IssueScope.CROSS_DEPUTY, "N-CEO"),
    ],
)
def test_seed_issue_positions(issue_id, layer, depth, scope, target) -> None:
    issue = next(i for i in seed_issues() if str(i.identifier) == issue_id)
    pos = issue.relative_position(org_directory())
    assert (pos.owner_layer, pos.owner_depth, pos.scope, pos.escalation_target) == (layer, depth, scope, target)
    assert pos.is_cross_unit


@pytest.mark.parametrize(
    ("code", "scope", "target"),
    [("HW", IssueScope.CROSS_UNIT, "N-HW"), ("WIN", IssueScope.LOCAL, "N-SW-WIN"),
     ("WEB", IssueScope.CROSS_UNIT, "N-SW"), ("LEG", IssueScope.CROSS_UNIT, "N-BRD")],
)
def test_azarpakhsh_subissue_positions(code, scope, target) -> None:
    pos = azarpakhsh().subissue_position(code, org_directory())
    assert pos.scope is scope and pos.escalation_target == target


def test_local_issue_is_answered_by_its_owner() -> None:
    issue = Issue.create(IssueId("AR-ISS-060"), "Deputy-internal planning", N("N-SW"), affected_nodes=(N("N-SW-WEB"), N("N-SW-MOB")))
    pos = issue.relative_position(org_directory())
    assert pos.is_local and pos.escalation_action == "answer" and pos.escalation_target == "N-SW"
    assert pos.common_ancestor == "N-SW"


def test_single_node_issue_is_local() -> None:
    issue = Issue.create(IssueId("AR-ISS-061"), "Driver packaging", N("N-SW-WIN"))
    pos = issue.relative_position(org_directory())
    assert pos.scope is IssueScope.LOCAL and pos.involved == ("N-SW-WIN",)


def test_position_with_unknown_node_raises() -> None:
    issue = Issue.create(IssueId("AR-ISS-062"), "x", N("N-SW-AI"))
    with pytest.raises(NotFoundError):
        issue.relative_position(org_directory())


def test_retired_node_is_not_in_the_directory() -> None:
    loaded = load_and_validate(REGISTRY_DIR)
    HierarchyWorkflowService(loaded.organization, loaded.ownership).retire_node(N("N-SW-VIS"))
    org = HierarchyOrgDirectory(loaded.organization)
    assert not org.exists("N-SW-VIS")
    issue = Issue.create(IssueId("AR-ISS-063"), "Logo", N("N-SW-UX"), affected_nodes=(N("N-SW-VIS"),))
    with pytest.raises(NotFoundError, match="N-SW-VIS"):
        issue.assert_nodes_exist(org)
