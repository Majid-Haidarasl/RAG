import pytest

from rag_core.ike.domain.model import IkeGraph, IkeRelation, RelationConfidence, RelationType
from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.identifiers import NodeIdentifier

pytestmark = pytest.mark.ike


def test_relation_created_between_issue_and_knowledge() -> None:
    graph = IkeGraph(NodeIdentifier("N-LIB"))
    graph.add(
        IkeRelation(
            "AR-ISS-024/WIN",
            "AR-SW-019",
            RelationType.RELATES_TO,
            RelationConfidence(0.9),
        )
    )
    graph.add(
        IkeRelation(
            "EX-ROOZBEH-MOHSENI",
            "AR-ISS-024/WIN",
            RelationType.CAN_HANDLE,
            RelationConfidence(0.95),
        )
    )
    assert len(graph.relations) == 2
    assert any(e.name == "RelationCreated" for e in graph.events)


def test_duplicate_and_reflexive_relations_are_rejected() -> None:
    graph = IkeGraph(NodeIdentifier("N-LIB"))
    rel = IkeRelation("A", "B", RelationType.EVIDENCE_FOR, RelationConfidence(1.0))
    graph.add(rel)
    with pytest.raises(InvariantError, match="duplicate"):
        graph.add(rel)
    with pytest.raises(InvariantError, match="reflexive"):
        IkeRelation("A", "A", RelationType.RELATES_TO, RelationConfidence(0.1))


def test_knowledge_lack_emits_dedicated_event() -> None:
    graph = IkeGraph(NodeIdentifier("N-HW-REP"))
    graph.add(IkeRelation("AR-ISS-024/HW", "photo-diagnosis", RelationType.KNOWLEDGE_LACK, RelationConfidence(0.8)))
    assert graph.events[-1].name == "KnowledgeLackFlagged"
