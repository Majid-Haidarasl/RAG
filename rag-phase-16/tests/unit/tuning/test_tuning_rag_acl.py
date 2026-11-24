"""Phase 14 ACL to retrieval / Q&A: samples, variant configs, ranking rows, grounding and scope."""

from dataclasses import replace

import pytest

from rag_core.rag.domain.records import ChunkRecord
from rag_core.rag.domain.retriever import RetrievalConfig
from rag_core.tuning.domain.gold import Evidence
from rag_core.tuning.infrastructure.config import RetrievalVariant
from rag_core.tuning.infrastructure.rag_acl import (
    CachingEmbedder,
    document_texts,
    gold_grounding,
    norm_text,
    quote_in,
    rank_items,
    retrieval_config,
    scope_problems,
    to_sample,
)
from tests.fixtures.tuning.samples import (
    CountingEmbedder,
    FakeScope,
    answered_item,
    refusal_item,
)

pytestmark = [pytest.mark.tuning, pytest.mark.retrieval]

QUOTE = "Priority 1 is complete service outage: response within 30 minutes and temporary restoration within 4 hours."


def record(doc: str, lang: str, order: int, text: str) -> ChunkRecord:
    return ChunkRecord(
        key=f"{doc}/{lang}#{order}",
        document_id=doc,
        language=lang,
        version="1",
        order=order,
        text=text,
    )


def test_to_sample_keeps_the_expectations() -> None:
    s = to_sample(answered_item("en"))
    assert (s.id, s.node, s.language, s.expected_status, s.case) == (
        "T-P01-en",
        "N-SW-SUP",
        "en",
        "answered",
        "P01",
    )
    assert s.expected_docs == ("AR-SW-022",) and s.expected_facts == (("30",), ("4",))
    r = to_sample(refusal_item("fa"))
    assert (
        r.expected_outside_docs == ("AR-HR-005",) and r.expected_escalation == "N-CEO"
    )


def test_retrieval_config_from_a_variant() -> None:
    base = RetrievalConfig(rrf_k=50, probe_k=2)
    cfg = retrieval_config(
        RetrievalVariant("wide", top_k=8, candidate_k=40, lexical_weight=1.5), base
    )
    assert (cfg.top_k, cfg.candidate_k, cfg.lexical_weight, cfg.vector_weight) == (
        8,
        40,
        1.5,
        1.0,
    )
    assert (cfg.rrf_k, cfg.probe_k) == (50, 2)


def test_norm_text_and_quote_in() -> None:
    assert norm_text("Response  within\n30 minutes.") == norm_text(
        "response within 30 minutes"
    )
    chunks = [norm_text("Intro. " + QUOTE), norm_text("Other text.")]
    assert quote_in(QUOTE, chunks) and not quote_in(
        "Response within 15 minutes.", chunks
    )
    assert not quote_in("  ", chunks)


def test_document_texts_orders_active_chunks() -> None:
    texts = document_texts(
        [
            record("AR-SW-022", "en", 2, "second"),
            record("AR-SW-022", "en", 1, "first"),
            replace(record("AR-SW-022", "en", 3, "gone"), status="retired"),
        ]
    )
    assert texts == {("AR-SW-022", "en"): ["first", "second"]}


def test_gold_grounding_clean() -> None:
    docs = document_texts([record("AR-SW-022", "en", 1, "Header. " + QUOTE)])
    assert gold_grounding([answered_item("en")], docs) == []


def test_gold_grounding_problems() -> None:
    docs = document_texts([record("AR-SW-022", "en", 1, "Something else entirely.")])
    item = answered_item(
        "en", reference_answer="Within 30 minutes and 4 hours, fine 900 [AR-SW-022 §1]."
    )
    codes = {p.code for p in gold_grounding([item], docs)}
    assert codes == {"quote_not_in_corpus", "unsupported_claim"}
    lost = answered_item("en", evidence=(Evidence("AR-ZZ-001", "en", QUOTE),))
    assert {p.code for p in gold_grounding([lost], docs)} >= {"unknown_document"}


def test_gold_grounding_fact_not_in_quote() -> None:
    docs = document_texts([record("AR-SW-022", "en", 1, "Response within 30 minutes.")])
    item = answered_item(
        "en", evidence=(Evidence("AR-SW-022", "en", "Response within 30 minutes."),)
    )
    problems = gold_grounding([item], docs)
    assert [p.code for p in problems if p.code == "fact_not_in_quote"] == [
        "fact_not_in_quote"
    ]
    assert str(problems[0]).startswith("T-P01-en:")


def test_scope_problems() -> None:
    scope = FakeScope(
        {"N-SW-SUP": {"AR-SW-022"}, "N-SW-WEB": {"AR-SW-016"}},
        {"AR-HR-005": "N-ADM-HR"},
    )
    assert scope_problems([answered_item("en"), refusal_item("en")], scope) == []
    hidden = answered_item("en", node="N-SW-WEB")
    assert scope_problems([hidden], scope) == ["T-P01-en:not_visible:AR-SW-022"]
    assert scope_problems([answered_item("en", node="N-NOPE")], scope) == [
        "T-P01-en:unknown_node"
    ]
    wrong_route = FakeScope(scope.visible, scope.owners, target="N-SW")
    assert scope_problems([refusal_item("en")], wrong_route) == [
        "T-P09-en:route:escalate->N-SW"
    ]
    no_owner = FakeScope(scope.visible, {})
    assert scope_problems([refusal_item("en")], no_owner) == ["T-P09-en:no_owner"]


def test_scope_flags_visible_outside_documents() -> None:
    scope = FakeScope({"N-SW-WEB": {"AR-HR-005"}}, {"AR-HR-005": "N-ADM-HR"})
    assert "T-P09-en:visible_outside:AR-HR-005" in scope_problems(
        [refusal_item("en")], scope
    )


class FakeResult:
    def __init__(self, docs: list[str]) -> None:
        self.docs = docs

    def document_ids(self) -> list[str]:
        return list(dict.fromkeys(self.docs))


def test_rank_items_skips_refusals_and_counts_violations() -> None:
    scope = FakeScope({"N-SW-SUP": {"AR-SW-022"}, "N-SW-WEB": set()}, {})
    rows = rank_items(
        [answered_item("en"), refusal_item("en")],
        lambda item: (FakeResult(["AR-SW-022", "AR-HR-005"]), "within 30 minutes"),
        scope,
    )
    assert len(rows) == 1
    row = rows[0]
    assert row.ranked == ("AR-SW-022", "AR-HR-005") and row.first_rank == 1
    assert row.context_facts == (1, 2) and row.scope_violations == 1


def test_caching_embedder_embeds_each_text_once() -> None:
    inner = CountingEmbedder()
    emb = CachingEmbedder(inner)
    first = emb.embed(["a", "bb", "a"])
    second = emb.embed(["bb", "ccc"])
    assert first == [[1.0, 1.0], [2.0, 1.0], [1.0, 1.0]] and second == [
        [2.0, 1.0],
        [3.0, 1.0],
    ]
    assert (
        inner.seen == [["a", "bb"], ["ccc"]] and emb.calls == 2 and emb.batch_size == 16
    )
