"""Sample questions and live-demo metrics."""

import json
from pathlib import Path

import pytest

from rag_core.qa.application.evaluation import (
    SampleQuestion,
    facts_found,
    hit_at_k,
    load_samples,
    qa_metrics,
    reciprocal_rank,
    retrieval_metrics,
    status_ok,
)
from rag_core.qa.domain.model import QaAnswer, QaStatus
from rag_core.rag.domain.ports import EscalationRoute
from rag_core.rag.domain.records import SearchFilters
from rag_core.rag.domain.retriever import Hit, OutOfScopeEvidence, RetrievalResult
from tests.fixtures.rag.fakes import rec

pytestmark = [pytest.mark.qa]

ROOT = Path(__file__).resolve().parents[3]


def result(*docs: str, outside: tuple[str, ...] = ()) -> RetrievalResult:
    hits = [Hit(rec(d, i, "t"), i + 1, 1.0) for i, d in enumerate(docs)]
    return RetrievalResult("q", "N-CEO", SearchFilters(), hits=hits, out_of_scope=[OutOfScopeEvidence(d, "N-X", 5.0, 0.7) for d in outside])


def sample(**kw) -> SampleQuestion:  # noqa: ANN003
    base = dict(id="Q", node="N-CEO", language="en", question="q", expected_status="answered")
    return SampleQuestion(**(base | kw))


def answer(status: QaStatus, text: str = "", escalation: EscalationRoute | None = None) -> QaAnswer:
    return QaAnswer("q", "N", "en", status, text, escalation=escalation, timings_s={"retrieval": 0.01, "generation": 2.0})


def test_shipped_samples_cover_brief() -> None:
    samples = load_samples(ROOT / "data" / "rag" / "sample-questions.json")
    assert 8 <= len(samples) <= 10
    assert {s.language for s in samples} == {"fa", "en"}
    assert len({s.node for s in samples}) >= 5
    assert any(s.case == "azarpakhsh" for s in samples)
    assert sum(s.expected_status == "out_of_scope" for s in samples) == 1
    assert sum(s.expected_status == "not_found" for s in samples) == 1
    assert all(s.expected_docs for s in samples if s.expected_status == "answered")


def test_sample_validation(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        sample(expected_status="maybe")
    with pytest.raises(ValueError):
        sample(language="de")
    path = tmp_path / "q.json"
    q = {"id": "Q1", "node": "N", "language": "en", "question": "x", "expected_status": "answered"}
    path.write_text(json.dumps({"questions": [q, q]}), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_samples(path)


def test_hit_and_reciprocal_rank() -> None:
    r = result("AR-HR-004", "AR-HR-005", "AR-SW-022")
    assert hit_at_k(r, ("AR-HR-005",)) is True and reciprocal_rank(r, ("AR-HR-005",)) == 0.5
    assert hit_at_k(r, ("AR-FIN-010",)) is False and reciprocal_rank(r, ("AR-FIN-010",)) == 0.0
    assert hit_at_k(r, ()) is None and reciprocal_rank(r, ()) is None
    assert hit_at_k(result(*["AR-X-001"] * 5, "AR-HR-005"), ("AR-HR-005",), k=5) is False


def test_facts_found_alternatives_and_digits() -> None:
    assert facts_found("پاسخ ظرف ۳۰ دقیقه و بازیابی ظرف چهار ساعت", (("30", "سی"), ("4", "چهار"))) == (2, 2)
    assert facts_found("Scores were 78.8 and 75.2.", (("78.8",), ("75.2",), ("99",))) == (2, 3)
    assert facts_found("RAM3 only", (("RAM",),)) == (0, 1), "whole tokens only"


def test_status_ok_rules() -> None:
    oos = sample(expected_status="out_of_scope", expected_escalation="N-CEO")
    assert status_ok(oos, answer(QaStatus.OUT_OF_SCOPE, escalation=EscalationRoute("escalate", "N-CEO", "r")))
    assert not status_ok(oos, answer(QaStatus.OUT_OF_SCOPE, escalation=EscalationRoute("escalate", "N-SW", "r")))
    nf = sample(expected_status="not_found")
    assert status_ok(nf, answer(QaStatus.NOT_FOUND_IN_SCOPE)) and status_ok(nf, answer(QaStatus.INSUFFICIENT_CONTEXT))
    assert not status_ok(nf, answer(QaStatus.ANSWERED))


def test_retrieval_metrics() -> None:
    rows = [(sample(expected_docs=("A-B-001",)), result("A-B-001")),
            (sample(expected_docs=("A-B-002",)), result("A-B-009", "A-B-002")),
            (sample(expected_status="out_of_scope", expected_outside_docs=("AR-HR-005",)), result(outside=("AR-HR-005",)))]
    m = retrieval_metrics(rows).to_dict()
    assert m == {"hit_at_5": 1.0, "mrr": 0.75, "scored": 2, "outside_detected": "1/1"}


def test_qa_metrics() -> None:
    from rag_core.qa.domain.citations import ParsedCitation, VerifiedCitation

    good = answer(QaStatus.ANSWERED, "30 minutes [AR-SW-022 §3]")
    good.citations = [VerifiedCitation(ParsedCitation("[AR-SW-022 §3]", "AR-SW-022", 3), True, "chunk")]
    rows = [(sample(expected_facts=(("30",),)), good),
            (sample(expected_status="out_of_scope"), answer(QaStatus.OUT_OF_SCOPE)),
            (sample(expected_status="not_found"), answer(QaStatus.ANSWERED, "made up"))]
    m = qa_metrics(rows)
    d = m.to_dict()
    assert d["questions"] == 3 and d["status_ok"] == 2 and d["answered"] == 2 and d["grounded"] == 1
    assert d["citation_validity"] == 1.0 and d["scope_handling"] == "1/2" and d["facts"] == "1/1"
    assert d["generation_avg_s"] == 2.0 and len(m.per_question) == 3
