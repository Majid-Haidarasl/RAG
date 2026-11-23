"""Retrieval orchestration: scope, filters, hybrid fusion, dedup, probe."""

import pytest

from rag_core.rag.application.indexing import build_retriever
from rag_core.rag.domain.lexical import Bm25Index
from rag_core.rag.domain.records import SearchFilters
from rag_core.rag.domain.retriever import HybridRetriever, RetrievalConfig
from rag_core.rag.domain.vector import InMemoryVectorIndex
from rag_core.rag.infrastructure.memory import InMemoryChunkStore
from rag_core.shared_kernel.errors import InvariantError, NotFoundError
from tests.fixtures.rag.fakes import FakeEmbedder, rec, sample_records, sample_scope

pytestmark = [pytest.mark.rag, pytest.mark.retrieval]


def hybrid(records=None, scope=None, config=None):  # noqa: ANN001, ANN201
    records = records if records is not None else sample_records()
    emb = FakeEmbedder()
    vectors = InMemoryVectorIndex()
    for r in records:
        if r.is_active:
            vectors.upsert(r.key, emb.vector(r.text))
    retriever = build_retriever(records, vectors=vectors, embedder=emb,
                                scope=scope if scope is not None else sample_scope(), config=config)
    return retriever, emb


def test_hybrid_mode_and_lexical_mode() -> None:
    assert hybrid()[0].mode == "hybrid"
    assert build_retriever(sample_records()).mode == "lexical"


def test_vector_index_and_embedder_must_come_together() -> None:
    with pytest.raises(InvariantError):
        HybridRetriever(InMemoryChunkStore(), Bm25Index(), vectors=InMemoryVectorIndex(), embedder=None)


def test_config_validation() -> None:
    with pytest.raises(InvariantError):
        RetrievalConfig(top_k=0)
    with pytest.raises(InvariantError):
        RetrievalConfig(top_k=10, candidate_k=5)


def test_node_sees_only_its_scope() -> None:
    r, _ = hybrid()
    res = r.retrieve("مرخصی ساعتی", "N-SUP")
    assert res.hits, "issue file is visible everywhere"
    assert all(h.record.document_id in {"AR-SW-022", "AR-ISS-024"} for h in res.hits)


def test_owner_node_finds_its_document_first() -> None:
    r, _ = hybrid()
    res = r.retrieve("سقف مرخصی ساعتی در روز", "N-HR")
    assert res.hits[0].record.document_id == "AR-HR-005"
    assert res.hits[0].rank == 1 and res.hits[0].lexical_rank is not None and res.hits[0].vector_rank is not None


def test_out_of_scope_probe_reports_owner_without_text() -> None:
    r, _ = hybrid()
    res = r.retrieve("مرخصی ساعتی", "N-SUP")
    assert any(e.document_id == "AR-HR-005" and e.owner_node == "N-HR" for e in res.out_of_scope)
    assert not hasattr(res.out_of_scope[0], "text")


def test_probe_can_be_disabled() -> None:
    r, _ = hybrid()
    assert r.retrieve("مرخصی ساعتی", "N-SUP", probe_outside=False).out_of_scope == []


def test_ceo_sees_everything_so_no_probe() -> None:
    r, _ = hybrid()
    assert r.retrieve("leave", "N-CEO").out_of_scope == []


def test_unknown_node_rejected() -> None:
    r, _ = hybrid()
    with pytest.raises(NotFoundError):
        r.retrieve("leave", "N-NOPE")


def test_empty_query_rejected() -> None:
    r, _ = hybrid()
    with pytest.raises(InvariantError):
        r.retrieve("   ", "N-HR")


def test_retired_chunks_never_returned() -> None:
    r, _ = hybrid()
    res = r.retrieve("level 1 repair working days", "N-REP")
    assert res.hits and all(h.record.version == "1.0" for h in res.hits)


def test_language_filter_applies_to_hits_and_probe() -> None:
    r, _ = hybrid()
    res = r.retrieve("hourly leave", "N-SUP", SearchFilters.of(languages=["en"]))
    assert all(h.record.language == "en" for h in res.hits)
    assert {e.document_id for e in res.out_of_scope} <= {"AR-HR-005", "AR-HW-012"}


def test_document_and_class_filters() -> None:
    r, _ = hybrid()
    res = r.retrieve("RAID RAM", "N-CEO", SearchFilters.of(document_ids=["AR-ISS-024"]))
    assert {h.record.document_id for h in res.hits} == {"AR-ISS-024"}
    res = r.retrieve("response", "N-CEO", SearchFilters.of(knowledge_classes=["sla"]))
    assert {h.record.document_id for h in res.hits} == {"AR-SW-022"}


def test_layer_filter() -> None:
    r, _ = hybrid()
    res = r.retrieve("RAID Azarpakhsh repair leave", "N-CEO", SearchFilters.of(layers=[4]))
    assert {h.record.layer for h in res.hits} == {4}


def test_cross_language_vector_match() -> None:
    r, _ = hybrid()
    res = r.retrieve("hourly leave", "N-HR", SearchFilters.of(languages=["fa"]))
    assert res.hits and res.hits[0].record.document_id == "AR-HR-005"
    assert res.hits[0].lexical_score is None and res.hits[0].vector_score is not None


def test_top_k_and_ranks_are_contiguous() -> None:
    r, _ = hybrid()
    res = r.retrieve("leave priority repair RAID", "N-CEO", top_k=3)
    assert len(res.hits) <= 3
    assert [h.rank for h in res.hits] == list(range(1, len(res.hits) + 1))


def test_query_embedded_once_per_retrieval() -> None:
    r, emb = hybrid()
    before = emb.calls
    r.retrieve("مرخصی ساعتی", "N-SUP")
    assert emb.calls == before + 1


def test_timings_and_candidates_reported() -> None:
    r, _ = hybrid()
    res = r.retrieve("leave", "N-HR")
    assert {"embed_query", "search", "total"} <= set(res.timings_s)
    assert res.candidates == 5  # active: HR-005 fa x2 + en, ISS-024 fa + en
    assert res.document_ids()[0] in {"AR-HR-005", "AR-ISS-024"}


def test_exact_duplicate_group_collapsed() -> None:
    base = sample_records()
    a = rec("AR-HR-004", 1, "کنترل مرز: پیش از اقدام، واقعیت سازمانی را جدا کنید.", owner="N-HR", content_hash="h1")
    b = rec("AR-HR-006", 1, "کنترل مرز: پیش از اقدام، واقعیت سازمانی را جدا کنید.", owner="N-HR", content_hash="h1",
            duplicate_of=a.key)
    scope = sample_scope()
    scope.visible["N-HR"] |= {"AR-HR-004", "AR-HR-006"}
    r, _ = hybrid(base + [a, b], scope)
    res = r.retrieve("کنترل مرز واقعیت سازمانی", "N-HR")
    keys = [h.key for h in res.hits]
    assert (a.key in keys) != (b.key in keys)
    assert res.duplicates_dropped and res.duplicates_dropped[0][0] in {a.key, b.key}


def test_near_duplicate_collapsed_by_shingle_jaccard() -> None:
    text = "the board approves contracts above two thousand million toman after legal review and finance check"
    a = rec("AR-LEG-009", 1, text, lang="en", owner="N-HR")
    b = rec("AR-BRD-003", 1, text + " today", lang="en", owner="N-HR")
    scope = sample_scope()
    scope.visible["N-HR"] |= {"AR-LEG-009", "AR-BRD-003"}
    r, _ = hybrid(sample_records() + [a, b], scope)
    res = r.retrieve("board approves contracts thousand million", "N-HR")
    assert len([h for h in res.hits if h.key in {a.key, b.key}]) == 1


def test_fa_en_pair_is_never_collapsed() -> None:
    r, _ = hybrid()
    res = r.retrieve("RAID RAM Windows Azarpakhsh آذرپخش", "N-LIB")
    langs = {h.record.language for h in res.hits if h.record.document_id == "AR-ISS-024"}
    assert langs == {"fa", "en"}


def test_lexical_only_retriever_works_without_embedder() -> None:
    r = build_retriever(sample_records(), scope=sample_scope())
    res = r.retrieve("Priority 1 response minutes", "N-SUP")
    assert res.hits[0].record.document_id == "AR-SW-022"
    assert res.hits[0].vector_score is None and res.best_vector is None and res.best_lexical > 0
    assert "embed_query" not in res.timings_s


def test_without_scope_everything_admitted() -> None:
    r = build_retriever(sample_records())
    res = r.retrieve("leave", None)
    assert res.out_of_scope == [] and res.candidates == 8


def test_hit_to_dict_is_json_friendly() -> None:
    import json

    r, _ = hybrid()
    res = r.retrieve("leave", "N-HR")
    json.dumps([h.to_dict() for h in res.hits])
