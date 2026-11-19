"""Node-scoped Q&A use case with fakes (no Ollama)."""

from pathlib import Path

import pytest

from rag_core.qa.application.service import NodeScopedQaService, QaConfig
from rag_core.qa.domain.model import QaRequest, QaStatus
from rag_core.qa.infrastructure.prompt_yaml import load_qa_prompts
from rag_core.rag.application.indexing import build_retriever
from rag_core.rag.domain.context import ContextAssembler
from rag_core.rag.domain.model import AnswerKind
from rag_core.rag.domain.records import SearchFilters
from rag_core.rag.domain.vector import InMemoryVectorIndex
from rag_core.shared_kernel.errors import InvariantError
from tests.fixtures.rag.fakes import FakeChat, FakeEmbedder, sample_records, sample_scope

pytestmark = [pytest.mark.qa]

PROMPTS = load_qa_prompts(Path(__file__).resolve().parents[3] / "config" / "prompts" / "qa")


def lexical_service(reply="INSUFFICIENT_CONTEXT") -> tuple[NodeScopedQaService, FakeChat]:  # noqa: ANN001
    chat = FakeChat(reply)
    retriever = build_retriever(sample_records(), scope=sample_scope())
    return NodeScopedQaService(retriever, ContextAssembler(), chat, PROMPTS,
                               config=QaConfig(evidence_min_lexical=2.0), model_name="fake-chat"), chat


def hybrid_service(reply="INSUFFICIENT_CONTEXT", threshold=0.6) -> tuple[NodeScopedQaService, FakeChat]:  # noqa: ANN001
    records = sample_records()
    emb = FakeEmbedder()
    index = InMemoryVectorIndex()
    active = [r for r in records if r.is_active]
    for r, v in zip(active, emb.embed([r.text for r in active]), strict=True):
        index.upsert(r.key, v)
    chat = FakeChat(reply)
    retriever = build_retriever(records, vectors=index, embedder=emb, scope=sample_scope())
    return NodeScopedQaService(retriever, ContextAssembler(), chat, PROMPTS,
                               config=QaConfig(evidence_min_vector=threshold)), chat


def test_grounded_answer_with_verified_citation_and_facts() -> None:
    svc, chat = lexical_service("مرخصی ساعتی حداکثر ۴ ساعت در روز و ۱۶ ساعت در ماه است [AR-HR-005 §1].")
    ans = svc.ask(QaRequest("سقف مرخصی ساعتی چقدر است؟", "N-HR"))
    assert ans.status is QaStatus.ANSWERED and ans.language == "fa"
    assert ans.grounded and [c.citation.label for c in ans.valid_citations] == ["AR-HR-005 §1"]
    assert ans.fact_check.all_supported and ans.fact_flags == []
    assert ans.model == "fake-chat" and ans.prompt_version == "2.0.0"
    assert {"retrieval", "generation", "total"} <= set(ans.timings_s)
    system, user = chat.calls[0]
    assert "Persian" in system and "[AR-HR-005 §1]" in user and "N-HR" in system


def test_prompt_context_only_contains_scope_documents() -> None:
    svc, chat = lexical_service("x [AR-SW-022 §3]")
    svc.ask(QaRequest("Priority 1 response time?", "N-SUP"))
    _, user = chat.calls[0]
    assert "AR-SW-022" in user and "AR-HR-005" not in user and "AR-HW-012" not in user


def test_invalid_citation_makes_answer_ungrounded() -> None:
    svc, _ = lexical_service("The limit is 4 hours [AR-HR-005 §9] [AR-BRD-003 §1].")
    ans = svc.ask(QaRequest("What is the hourly leave limit?", "N-HR"))
    assert ans.status is QaStatus.ANSWERED and not ans.grounded and len(ans.invalid_citations) == 2
    assert ans.to_rag_answer().kind is AnswerKind.ABSTAINED


def test_answer_without_citation_is_not_grounded() -> None:
    svc, _ = lexical_service("Four hours per day.")
    ans = svc.ask(QaRequest("What is the hourly leave limit?", "N-HR"))
    assert ans.status is QaStatus.ANSWERED and ans.citations == [] and not ans.grounded


def test_fact_flag_for_number_not_in_cited_chunk() -> None:
    svc, _ = lexical_service("Hourly leave is 6 hours per day [AR-HR-005 §1].")
    ans = svc.ask(QaRequest("What is the hourly leave limit?", "N-HR"))
    assert any(f.endswith(":6:unsupported") for f in ans.fact_flags)


def test_out_of_scope_escalates_without_calling_model() -> None:
    svc, chat = lexical_service()
    ans = svc.ask(QaRequest("مرخصی بدون حقوق چند روز است؟", "N-SUP"))
    assert ans.status is QaStatus.OUT_OF_SCOPE and chat.calls == []
    assert ans.escalation is not None and ans.escalation.target == "N-CEO"
    assert "N-CEO" in ans.text and "۳۰" not in ans.text, "no out-of-scope content leaks"


def test_not_found_when_nothing_anywhere() -> None:
    svc, chat = lexical_service()
    ans = svc.ask(QaRequest("What is the pets policy?", "N-CEO"))
    assert ans.status is QaStatus.NOT_FOUND_IN_SCOPE and chat.calls == [] and ans.escalation is None
    assert ans.language == "en" and "N-CEO" in ans.text


def test_model_refusal_becomes_insufficient_context() -> None:
    svc, chat = lexical_service("INSUFFICIENT_CONTEXT the context has no such rule")
    ans = svc.ask(QaRequest("Priority 1 response time?", "N-SUP"))
    assert len(chat.calls) == 1 and ans.status is QaStatus.INSUFFICIENT_CONTEXT
    assert ans.raw_model_text.startswith("INSUFFICIENT_CONTEXT")


def test_model_refusal_escalates_when_outside_is_stronger() -> None:
    svc, _ = lexical_service("INSUFFICIENT_CONTEXT")
    ans = svc.ask(QaRequest("Level 1 repair مرخصی بدون حقوق تأیید معاون", "N-REP"))
    assert ans.status is QaStatus.OUT_OF_SCOPE and ans.escalation.target == "N-CEO"


def test_hybrid_mode_out_of_scope_and_answer() -> None:
    svc, chat = hybrid_service()
    ans = svc.ask(QaRequest("مرخصی بدون حقوق چند روز است؟", "N-SUP"))
    assert ans.status is QaStatus.OUT_OF_SCOPE and ans.escalation.target == "N-CEO" and chat.calls == []
    svc, chat = hybrid_service("Azarpakhsh is late due to RAID and RAM [AR-ISS-024 §5/en].", threshold=0.45)
    ans = svc.ask(QaRequest("Azarpakhsh delay cause", "N-REP"))
    assert ans.status is QaStatus.ANSWERED and ans.grounded


def test_filters_pass_through_to_retrieval() -> None:
    svc, chat = lexical_service("x [AR-SW-022 §3]")
    svc.ask(QaRequest("Priority 1 response time?", "N-SUP", filters=SearchFilters.of(languages=["en"])))
    _, user = chat.calls[0]
    assert "Priority 1 is complete outage" in user and "اولویت" not in user


def test_bridge_to_phase3_answer_and_dict() -> None:
    svc, _ = lexical_service("Hourly leave is limited to 4 hours per day [AR-HR-005 §1/en].")
    ans = svc.ask(QaRequest("What is the hourly leave limit?", "N-HR"))
    rag = ans.to_rag_answer()
    assert rag.kind is AnswerKind.GROUNDED and rag.citations[0].chunk_id == "AR-HR-005#c0001"
    d = ans.to_dict()
    assert d["status"] == "answered" and d["grounded"] is True and d["citations"][0]["valid"]


def test_refusal_bridges_to_abstained() -> None:
    svc, _ = lexical_service()
    assert svc.ask(QaRequest("What is the pets policy?", "N-CEO")).to_rag_answer().kind is AnswerKind.ABSTAINED


@pytest.mark.parametrize("q,node", [("", "N-HR"), ("x", " ")])
def test_request_validation(q: str, node: str) -> None:
    with pytest.raises(InvariantError):
        QaRequest(q, node)
