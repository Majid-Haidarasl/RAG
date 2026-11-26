"""QaAnswer.related: unique document ids from retrieval, rank order, max 10."""

from __future__ import annotations

from rag_core.qa.application.service import RELATED_MAX, related_document_ids
from rag_core.rag.domain.records import ChunkRecord, SearchFilters
from rag_core.rag.domain.retriever import Hit, RetrievalResult


def _hit(doc: str, order: int = 1, rank: int = 1) -> Hit:
    record = ChunkRecord(
        key=f"{doc}#c{order:04d}",
        document_id=doc,
        language="en",
        version="1.0",
        order=order,
        text=f"chunk of {doc}",
        owner_node="N-LIB",
    )
    return Hit(
        record=record,
        rank=rank,
        fused_score=1.0 / rank,
        vector_score=0.9,
        lexical_score=5.0,
    )


def test_related_document_ids_unique_rank_order_capped() -> None:
    hits = [
        _hit("AR-HW-012", 1, rank=1),
        _hit("AR-HW-015", 1, rank=2),
        _hit("AR-HW-012", 2, rank=3),  # duplicate doc → skipped
        _hit("AR-SW-019", 1, rank=4),
    ]
    for i in range(1, 15):
        hits.append(_hit(f"AR-DOC-{i:03d}", 1, rank=4 + i))
    result = RetrievalResult(
        query="q", node="N-LIB", filters=SearchFilters(), hits=hits
    )
    related = related_document_ids(result)
    assert related[0:3] == ["AR-HW-012", "AR-HW-015", "AR-SW-019"]
    assert len(related) == RELATED_MAX
    assert len(set(related)) == RELATED_MAX
