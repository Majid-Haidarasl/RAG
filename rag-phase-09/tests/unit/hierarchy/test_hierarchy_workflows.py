"""Add / move / retire node workflows and knowledge reassignment on retire."""

import pytest

from rag_core.hierarchy.application.workflows import HierarchyWorkflowService
from rag_core.hierarchy.domain.model import Node, NodeStatus, NodeType
from rag_core.hierarchy.domain.ownership import DocumentOwnership, OwnershipLink, OwnershipRole
from rag_core.shared_kernel.errors import InvariantError, NotFoundError
from rag_core.shared_kernel.identifiers import DocumentId, NodeIdentifier
from rag_core.shared_kernel.layer import LayerIndex
from tests.fixtures.armanrayan import board, ceo, library, seed_organization, software_deputy, web_team
from tests.fixtures.hierarchy.registry import shipped_registry

pytestmark = [pytest.mark.hierarchy, pytest.mark.registry]

N = NodeIdentifier


def _team(node_id: str, parent: str = "N-SW") -> Node:
    return Node(N(node_id), "Data Team", "تیم داده", NodeType.TEAM, LayerIndex(3), N(parent), is_leaf=True)


def _service() -> HierarchyWorkflowService:
    loaded = shipped_registry()
    return HierarchyWorkflowService(loaded.organization, loaded.ownership)


def test_add_node_under_a_deputy() -> None:
    svc = _service()
    svc.add_node(_team("N-SW-DATA"))
    org = svc.organization
    assert org.path_string(N("N-SW-DATA")) == "N-BRD > N-CEO > N-SW > N-SW-DATA"
    assert len(org.nodes_on_layer(3)) == 16


def test_add_node_under_a_retired_parent_is_rejected() -> None:
    svc = _service()
    svc.retire_node(N("N-SW-VIS"))
    with pytest.raises(InvariantError, match="retired"):
        svc.add_node(Node(N("N-SW-VIS-X"), "Sub", "زیر", NodeType.TEAM, LayerIndex(3), N("N-SW-VIS")))


def test_move_team_to_another_deputy_keeps_layer_and_emits_event() -> None:
    svc = _service()
    moved = svc.move_node(N("N-SW-SUP"), N("N-HW"))
    assert moved.parent_id == N("N-HW") and moved.layer.value == 3
    assert any(e.name == "NodeMoved" and e.payload["to"] == "N-HW" for e in svc.organization.events)
    assert N("N-SW-SUP") not in {d.identifier for d in svc.organization.descendants(N("N-SW"))}


@pytest.mark.parametrize(
    ("node", "parent", "match"),
    [
        ("N-BRD", "N-CEO", "root"),
        ("N-SW-WEB", "N-SW", "already"),
        ("N-SW", "N-SW-WEB", "cycle"),
        ("N-SW-WEB", "N-CEO", "adjacent"),
        ("N-SW-WEB", "N-HW-REP", "leaf"),
        ("N-LIB", "N-SW", "adjacent"),
    ],
)
def test_invalid_moves_are_rejected(node: str, parent: str, match: str) -> None:
    with pytest.raises(InvariantError, match=match):
        _service().move_node(N(node), N(parent))


def test_move_to_unknown_parent_raises_not_found() -> None:
    with pytest.raises(NotFoundError):
        _service().move_node(N("N-SW-WEB"), N("N-XX"))


def test_retire_leaf_reassigns_owned_and_co_owned_knowledge_to_parent() -> None:
    svc = _service()
    changes = svc.retire_node(N("N-SW-WEB"), reason="merged")
    org, own = svc.organization, svc.ownership
    assert org.get(N("N-SW-WEB")).status is NodeStatus.RETIRED
    assert org.get(N("N-SW-WEB")).successor_id == N("N-SW")
    assert own.owner_of(DocumentId("AR-SW-017")) == N("N-SW")
    assert {c.document_id.value for c in changes} == {"AR-SW-017", "AR-TRN-026"}
    assert own.documents_of(N("N-SW-WEB")) == []
    assert any(e.name == "KnowledgeReassigned" for e in own.events)
    assert N("N-SW-WEB") not in {n.identifier for n in org.leaves()}


def test_retire_with_explicit_sibling_successor() -> None:
    svc = _service()
    svc.retire_node(N("N-SW-VIS"), N("N-SW-UX"))
    assert svc.ownership.owner_of(DocumentId("AR-SW-021")) == N("N-SW-UX")


def test_retire_node_with_active_children_is_rejected() -> None:
    with pytest.raises(InvariantError, match="active children"):
        _service().retire_node(N("N-SW"))


def test_retire_root_is_rejected() -> None:
    with pytest.raises(InvariantError, match="root"):
        _service().retire_node(N("N-BRD"))


def test_successor_must_be_active_and_not_the_node_itself() -> None:
    svc = _service()
    svc.retire_node(N("N-SW-VIS"))
    with pytest.raises(InvariantError, match="retired"):
        svc.retire_node(N("N-SW-UX"), N("N-SW-VIS"))
    with pytest.raises(InvariantError, match="itself"):
        svc.retire_node(N("N-SW-MOB"), N("N-SW-MOB"))


def test_retired_deputy_after_children_moved() -> None:
    svc = _service()
    for child in [c.identifier for c in svc.organization.active_children_of(N("N-HW"))]:
        svc.move_node(child, N("N-SW"))
    svc.retire_node(N("N-HW"))
    assert svc.ownership.co_owners_of(DocumentId("AR-HW-012")) == (N("N-CEO"),)
    assert len(svc.organization.nodes_on_layer(2)) == 2


def test_library_knowledge_goes_to_ceo_not_to_a_team() -> None:
    svc = _service()
    with pytest.raises(InvariantError, match="repository"):
        svc.retire_node(N("N-LIB"), N("N-SW-WEB"))
    svc.retire_node(N("N-LIB"))
    assert svc.ownership.owner_of(DocumentId("AR-ISS-024")) == N("N-CEO")


def test_reassign_drops_redundant_co_ownership() -> None:
    own = DocumentOwnership()
    d = DocumentId("AR-SW-017")
    own.add(OwnershipLink(d, N("N-SW-WEB"), OwnershipRole.OWNER))
    own.add(OwnershipLink(d, N("N-SW"), OwnershipRole.CO_OWNER))
    own.reassign(N("N-SW-WEB"), N("N-SW"))
    assert own.owner_of(d) == N("N-SW")
    assert own.co_owners_of(d) == ()


def test_two_owners_for_one_document_are_rejected() -> None:
    own = DocumentOwnership()
    d = DocumentId("AR-SW-017")
    own.add(OwnershipLink(d, N("N-SW-WEB"), OwnershipRole.OWNER))
    with pytest.raises(InvariantError, match="owner"):
        own.add(OwnershipLink(d, N("N-SW-MOB"), OwnershipRole.OWNER))


def test_q3_exemption_is_explicit_repository_under_deputy_is_rejected() -> None:
    org = seed_organization(board(), ceo(), software_deputy(), web_team())
    stray = Node(N("N-SW-LIB"), "Team Library", "کتابخانه تیم", NodeType.KNOWLEDGE_REPOSITORY, LayerIndex(4), N("N-SW"))
    with pytest.raises(InvariantError, match="adjacent"):
        org.register_node(stray)
    org.register_node(library())  # L4 repository under L1 CEO remains allowed
