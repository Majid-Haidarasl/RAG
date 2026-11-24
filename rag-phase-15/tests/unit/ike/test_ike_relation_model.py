"""IKE relation model (Phase 9): endpoint kinds, typing rules, queries, validation."""

import pytest

from rag_core.ike.domain.model import (
    EndpointKind,
    IkeGraph,
    IkeRelation,
    RelationConfidence,
    RelationType,
    endpoint_kind,
    relation_problems,
)
from rag_core.ike.infrastructure.memory import InMemoryIkeGraphRepository
from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.identifiers import NodeIdentifier

pytestmark = [pytest.mark.ike, pytest.mark.ike_model]


def rel(src: str, dst: str, kind: RelationType, conf: float = 1.0) -> IkeRelation:
    return IkeRelation(src, dst, kind, RelationConfidence(conf))


@pytest.mark.parametrize(
    ("identifier", "kind"),
    [
        ("AR-ISS-024", EndpointKind.ISSUE),
        ("AR-ISS-024/HW", EndpointKind.SUBISSUE),
        ("EX-SAEED-AKBARI", EndpointKind.EXECUTOR),
        ("AR-HW-012", EndpointKind.KNOWLEDGE),
        ("AR-CNT-1402-118", EndpointKind.KNOWLEDGE),
        ("gap:no-lead-executor", EndpointKind.TOPIC),
        ("photo-diagnosis", EndpointKind.TOPIC),
    ],
)
def test_endpoint_kind(identifier: str, kind: EndpointKind) -> None:
    assert endpoint_kind(identifier) is kind


def test_well_typed_relations_have_no_problems() -> None:
    for r in (
        rel("AR-ISS-024/HW", "AR-HW-012", RelationType.RELATES_TO),
        rel("EX-SAEED-AKBARI", "AR-ISS-024/HW", RelationType.CAN_HANDLE, 0.9),
        rel("AR-HW-012", "EX-SAEED-AKBARI", RelationType.EVIDENCE_FOR),
        rel("AR-ISS-024/WEB", "AR-RFP-025", RelationType.KNOWLEDGE_LACK, 0.8),
        rel("AR-ISS-024/WIN", "AR-ISS-024/HW", RelationType.DEPENDS_ON),
        rel("AR-ISS-024/HW", "AR-ISS-024", RelationType.PART_OF),
    ):
        assert relation_problems(r) == []


@pytest.mark.parametrize(
    ("relation", "fragment"),
    [
        (
            rel("AR-HW-012", "AR-ISS-024/HW", RelationType.CAN_HANDLE),
            "source kind knowledge",
        ),
        (
            rel("EX-SAEED-AKBARI", "AR-HW-012", RelationType.CAN_HANDLE),
            "target kind knowledge",
        ),
        (
            rel("AR-ISS-024/WIN", "AR-ISS-031/HW", RelationType.DEPENDS_ON),
            "inside one issue",
        ),
        (rel("AR-ISS-024/HW", "AR-ISS-031", RelationType.PART_OF), "own parent"),
        (
            rel("AR-ISS-024/HW", "EX-SAEED-AKBARI", RelationType.KNOWLEDGE_LACK),
            "target kind executor",
        ),
    ],
)
def test_ill_typed_relations_are_reported(relation: IkeRelation, fragment: str) -> None:
    problems = relation_problems(relation)
    assert problems and any(fragment in p for p in problems)


def test_add_checked_rejects_ill_typed_relation_but_add_stays_permissive() -> None:
    graph = IkeGraph(NodeIdentifier("N-LIB"))
    with pytest.raises(InvariantError, match="not allowed"):
        graph.add_checked(rel("AR-HW-012", "AR-ISS-024/HW", RelationType.CAN_HANDLE))
    graph.add(rel("A", "B", RelationType.EVIDENCE_FOR))
    assert len(graph.relations) == 1


def test_add_if_absent_skips_existing_relation() -> None:
    graph = IkeGraph(NodeIdentifier("N-LIB"))
    first = rel("AR-ISS-024/HW", "AR-HW-012", RelationType.RELATES_TO)
    assert graph.add_if_absent(first) is True
    assert (
        graph.add_if_absent(
            rel("AR-ISS-024/HW", "AR-HW-012", RelationType.RELATES_TO, 0.5)
        )
        is False
    )
    assert graph.relations == [first]


def test_queries_and_counts() -> None:
    graph = IkeGraph(NodeIdentifier("N-LIB"))
    graph.add_checked(rel("AR-ISS-024/HW", "AR-HW-012", RelationType.RELATES_TO))
    graph.add_checked(rel("AR-ISS-024/HW", "AR-HW-015", RelationType.RELATES_TO))
    graph.add_checked(
        rel("EX-SAEED-AKBARI", "AR-ISS-024/HW", RelationType.CAN_HANDLE, 0.9)
    )
    assert [
        r.target_id for r in graph.outgoing("AR-ISS-024/HW", RelationType.RELATES_TO)
    ] == ["AR-HW-012", "AR-HW-015"]
    assert [r.source_id for r in graph.incoming("AR-ISS-024/HW")] == ["EX-SAEED-AKBARI"]
    counts = graph.counts()
    assert (
        counts["relates_to"] == 2
        and counts["can_handle"] == 1
        and counts["part_of"] == 0
    )
    assert graph.endpoints() == {
        "issue": 0,
        "subissue": 1,
        "executor": 1,
        "knowledge": 2,
        "topic": 0,
    }
    data = graph.to_dict()
    assert data["node"] == "N-LIB" and len(data["relations"]) == 3  # type: ignore[arg-type]


def test_dependency_cycle_is_detected_by_validate() -> None:
    graph = IkeGraph(NodeIdentifier("N-LIB"))
    graph.add_checked(rel("AR-ISS-024/WIN", "AR-ISS-024/HW", RelationType.DEPENDS_ON))
    assert graph.dependency_cycle() == [] and graph.validate() == []
    graph.add_checked(rel("AR-ISS-024/HW", "AR-ISS-024/WIN", RelationType.DEPENDS_ON))
    cycle = graph.dependency_cycle()
    assert cycle[0] == cycle[-1]
    assert any("dependency cycle" in p for p in graph.validate())


def test_validate_reports_duplicates_and_bad_kinds_added_around_the_root() -> None:
    graph = IkeGraph(NodeIdentifier("N-LIB"))
    r = rel("AR-HW-012", "AR-ISS-024/HW", RelationType.CAN_HANDLE)
    graph.relations.extend([r, r])
    problems = graph.validate()
    assert any("duplicate" in p for p in problems) and any(
        "not allowed" in p for p in problems
    )


def test_knowledge_lack_on_topic_emits_event() -> None:
    graph = IkeGraph(NodeIdentifier("N-HW-REP"))
    graph.add_checked(
        rel("AR-ISS-024/HW", "gap:no-lead-executor", RelationType.KNOWLEDGE_LACK, 0.9)
    )
    assert graph.events[-1].name == "KnowledgeLackFlagged"


def test_in_memory_graph_repository() -> None:
    repo = InMemoryIkeGraphRepository()
    empty = repo.get(NodeIdentifier("N-LIB"))
    assert empty.relations == [] and len(repo) == 0
    graph = IkeGraph(NodeIdentifier("N-LIB"))
    graph.add_checked(rel("AR-ISS-024/HW", "AR-ISS-024", RelationType.PART_OF))
    repo.save(graph)
    assert repo.get(NodeIdentifier("N-LIB")) is graph and len(repo) == 1
