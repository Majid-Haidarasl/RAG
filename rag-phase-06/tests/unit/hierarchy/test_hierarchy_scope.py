"""Retrieval scope resolution, leaf boundaries and escalation routing."""

import pytest

from rag_core.hierarchy.application.workflows import HierarchyWorkflowService, catalog_index, scope_sizes
from rag_core.hierarchy.domain.scope import RoutingAction, ScopeResolver, leaf_boundary, route_question
from rag_core.hierarchy.domain.validation import normalize_confidentiality
from rag_core.shared_kernel.confidentiality import Confidentiality
from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.identifiers import NodeIdentifier
from tests.fixtures.hierarchy.registry import shipped_registry

pytestmark = [pytest.mark.hierarchy, pytest.mark.registry]

N = NodeIdentifier
CONF = {k: Confidentiality(normalize_confidentiality(v[1])) for k, v in catalog_index().items()}


@pytest.fixture()
def loaded():
    return shipped_registry()


def _visible(loaded, node: str) -> set[str]:
    resolver = ScopeResolver(loaded.organization)
    return {d.value for d in resolver.visible_documents(N(node), loaded.ownership, CONF)}


def test_scope_nodes_of_a_team(loaded) -> None:
    scope = ScopeResolver(loaded.organization).resolve(N("N-SW-WEB"))
    assert {str(n) for n in scope.visible_nodes} == {"N-SW-WEB", "N-SW", "N-CEO", "N-BRD", "N-LIB"}
    assert N("N-SW-MOB") not in scope.visible_nodes


def test_web_team_sees_own_parent_and_library_but_not_siblings_or_restricted(loaded) -> None:
    seen = _visible(loaded, "N-SW-WEB")
    assert {"AR-SW-017", "AR-SW-016", "AR-ISS-024", "AR-TRN-026", "AR-ORG-002"} <= seen
    assert "AR-SW-018" not in seen  # sibling mobile team
    assert "AR-BRD-003" not in seen  # restricted Board document of an ancestor
    assert "AR-EXE-023" not in seen  # restricted library item, WEB not a co-owner
    assert "AR-HW-012" not in seen  # other deputy


def test_restricted_item_visible_to_co_owner_and_its_chain_of_command(loaded) -> None:
    assert "AR-EXE-023" in _visible(loaded, "N-SW-WIN")  # co-owner
    assert "AR-EXE-023" in _visible(loaded, "N-SW")  # ancestor of co-owner
    assert "AR-EXE-023" in _visible(loaded, "N-HW")
    assert "AR-EXE-023" not in _visible(loaded, "N-ADM-FIN")


def test_hr_records_are_limited_to_hr_and_its_chain(loaded) -> None:
    assert "AR-HR-004" in _visible(loaded, "N-ADM-HR")
    assert "AR-HR-004" in _visible(loaded, "N-ADM")
    assert "AR-HR-004" in _visible(loaded, "N-CEO")
    assert "AR-HR-004" not in _visible(loaded, "N-SW")
    assert "AR-HR-004" not in _visible(loaded, "N-ADM-FIN")


def test_document_reader_link_opens_restricted_governing_document(loaded) -> None:
    assert "AR-BRD-003" in _visible(loaded, "N-CEO")
    assert "AR-HR-011" in _visible(loaded, "N-ADM-SRV")


def test_board_sees_everything(loaded) -> None:
    assert len(_visible(loaded, "N-BRD")) == 26


def test_public_items_are_always_visible(loaded) -> None:
    scope = ScopeResolver(loaded.organization).resolve(N("N-HW-SAL"))
    assert scope.can_see(N("N-ADM-FIN"), Confidentiality.PUBLIC)
    assert not scope.can_see(N("N-ADM-FIN"), Confidentiality.INTERNAL)


def test_retired_node_cannot_be_a_scope(loaded) -> None:
    svc = HierarchyWorkflowService(loaded.organization, loaded.ownership)
    svc.retire_node(N("N-SW-VIS"))
    with pytest.raises(InvariantError, match="retired"):
        ScopeResolver(loaded.organization).resolve(N("N-SW-VIS"))
    assert "AR-SW-021" in _visible(loaded, "N-SW")


def test_scope_sizes_cover_every_active_node(loaded) -> None:
    sizes = scope_sizes(loaded.organization, loaded.ownership, catalog_index())
    assert len(sizes) == 21
    assert sizes["N-BRD"]["visible_documents"] == 26
    assert sizes["N-SW-WEB"]["visible_documents"] < sizes["N-SW"]["visible_documents"]


def test_leaf_boundary_of_web_team(loaded) -> None:
    b = leaf_boundary(loaded.organization, N("N-SW-WEB"), loaded.ownership)
    assert [d.value for d in b.owned_documents] == ["AR-SW-017"]
    assert [d.value for d in b.co_owned_documents] == ["AR-TRN-026"]
    assert b.escalation_target == N("N-SW")
    with pytest.raises(InvariantError, match="not a leaf"):
        leaf_boundary(loaded.organization, N("N-SW"), loaded.ownership)


@pytest.mark.parametrize(
    ("asking", "owners", "reserved", "action", "target"),
    [
        ("N-SW-WEB", ["N-SW-WEB"], False, RoutingAction.ANSWER, "N-SW-WEB"),
        ("N-SW-WEB", ["N-SW-WEB", "N-LIB"], False, RoutingAction.ANSWER, "N-SW-WEB"),
        ("N-SW-WEB", ["N-SW-MOB"], False, RoutingAction.ESCALATE, "N-SW"),
        ("N-SW-WEB", ["N-HW-REP"], False, RoutingAction.ESCALATE, "N-CEO"),
        ("N-ADM-LEG", ["N-ADM-FIN", "N-SW"], False, RoutingAction.ESCALATE, "N-CEO"),
        ("N-SW", ["N-SW-WEB"], False, RoutingAction.ANSWER, "N-SW"),
        ("N-SW-WEB", ["N-SW-WEB"], True, RoutingAction.ESCALATE, "N-BRD"),
    ],
)
def test_route_question(loaded, asking, owners, reserved, action, target) -> None:
    decision = route_question(loaded.organization, N(asking), [N(o) for o in owners], reserved_decision=reserved)
    assert decision.action is action
    assert str(decision.target) == target
