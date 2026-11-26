"""IkeGraphBuilder: relations from views, referrals and comparisons."""

import pytest

from rag_core.ike.application.services import IkeService
from rag_core.ike.domain.builder import (
    GAP_NO_EVIDENCE,
    GAP_NO_LEAD,
    NOTE_LACK_SCOPE,
    NOTE_LACK_UNHELD,
    IkeGraphBuilder,
    suggestion_confidence,
)
from rag_core.ike.domain.comparison import compare_knowledge
from rag_core.ike.domain.model import RelationType
from tests.fixtures.ike.samples import sample_issue, sample_referrals, search_result

pytestmark = [pytest.mark.ike, pytest.mark.ike_model]


def _graph(comparisons=None):
    return IkeGraphBuilder().build(sample_issue(), sample_referrals(), comparisons)


def test_registry_only_graph_counts() -> None:
    graph = _graph()
    assert graph.counts() == {
        "relates_to": 8,
        "can_handle": 3,
        "evidence_for": 3,
        "knowledge_lack": 4,
        "depends_on": 1,
        "part_of": 3,
        "similar_issue": 0,
        "blocked_by": 0,
        "executor_worked_on": 0,
        "supports": 0,
        "conflicts": 0,
    }
    assert graph.validate() == []
    assert str(graph.node_id) == "N-LIB"


def test_issue_does_not_relate_to_its_own_file() -> None:
    targets = [
        r.target_id for r in _graph().outgoing("AR-ISS-050", RelationType.RELATES_TO)
    ]
    assert targets == ["AR-HW-012", "AR-SW-017"]


def test_structure_relations() -> None:
    graph = _graph()
    assert {r.source_id for r in graph.of_type(RelationType.PART_OF)} == {
        "AR-ISS-050/HW",
        "AR-ISS-050/WIN",
        "AR-ISS-050/WEB",
    }
    dep = graph.of_type(RelationType.DEPENDS_ON)
    assert [(r.source_id, r.target_id) for r in dep] == [
        ("AR-ISS-050/WIN", "AR-ISS-050/HW")
    ]


def test_executor_relations() -> None:
    graph = _graph()
    can = {r.source_id: r for r in graph.of_type(RelationType.CAN_HANDLE)}
    assert can["EX-SAEED-AKBARI"].target_id == "AR-ISS-050/HW"
    assert can["EX-SAEED-AKBARI"].confidence.value == 0.9 and can[
        "EX-SAEED-AKBARI"
    ].source_note.startswith("lead")
    assert can["EX-YASAMAN-KARAMI"].source_note.startswith("collaborator")
    evidence = sorted(
        (r.source_id, r.target_id) for r in graph.of_type(RelationType.EVIDENCE_FOR)
    )
    assert evidence == [
        ("AR-HW-012", "EX-SAEED-AKBARI"),
        ("AR-HW-015", "EX-SAEED-AKBARI"),
        ("AR-SW-019", "EX-ROOZBEH-MOHSENI"),
    ]


def test_knowledge_lacks() -> None:
    lacks = {
        (r.source_id, r.target_id): r
        for r in _graph().of_type(RelationType.KNOWLEDGE_LACK)
    }
    dep = lacks[("AR-ISS-050/WIN", "AR-HW-015")]
    assert (
        dep.confidence.value == 0.4 and "dependency on AR-ISS-050/HW" in dep.source_note
    )
    assert lacks[("AR-ISS-050/WEB", "AR-SW-017")].source_note == NOTE_LACK_UNHELD
    assert lacks[("AR-ISS-050/WEB", "AR-RFP-025")].confidence.value == 0.8
    assert ("AR-ISS-050/WEB", GAP_NO_LEAD) in lacks
    assert ("AR-ISS-050/HW", GAP_NO_LEAD) not in lacks


@pytest.mark.parametrize(
    ("rank", "confidence"), [(1, 0.7), (2, 0.6), (4, 0.4), (5, 0.3), (9, 0.3)]
)
def test_suggestion_confidence(rank: int, confidence: float) -> None:
    assert suggestion_confidence(rank) == confidence


def test_comparison_adds_suggestions_scope_lacks_and_evidence_gaps() -> None:
    hw = compare_knowledge(
        "AR-ISS-050/HW",
        ("AR-HW-012", "AR-HW-015"),
        search_result(
            "N-HW-REP", ["AR-HW-012", "AR-HW-013"], {"AR-HW-012", "AR-HW-013"}
        ),
    )
    web = compare_knowledge(
        "AR-ISS-050/WEB",
        ("AR-SW-017", "AR-RFP-025"),
        search_result(
            "N-SW-WEB", ["AR-SW-017"], {"AR-SW-017", "AR-RFP-025"}, lexical=1.0
        ),
    )
    graph = _graph({"AR-ISS-050/HW": hw, "AR-ISS-050/WEB": web})
    rel = {
        r.target_id: r for r in graph.outgoing("AR-ISS-050/HW", RelationType.RELATES_TO)
    }
    assert (
        rel["AR-HW-013"].confidence.value == 0.6
        and "not cited" in rel["AR-HW-013"].source_note
    )
    assert rel["AR-HW-012"].source_note.endswith("retrieved rank 1")
    assert rel["AR-HW-015"].source_note.endswith("not retrieved in scope")
    lacks = {
        (r.source_id, r.target_id): r
        for r in graph.of_type(RelationType.KNOWLEDGE_LACK)
    }
    assert lacks[("AR-ISS-050/HW", "AR-HW-015")].source_note == NOTE_LACK_SCOPE
    assert ("AR-ISS-050/WEB", GAP_NO_EVIDENCE) in lacks
    assert ("AR-ISS-050/HW", GAP_NO_EVIDENCE) not in lacks
    assert graph.validate() == []


def test_service_build_returns_a_valid_graph() -> None:
    graph = IkeService().build(sample_issue(), sample_referrals())
    assert len(graph.relations) == 22
