"""PromoteAnswer: judged QaAnswer → draft KnowledgeItem."""

from __future__ import annotations

from rag_core.judging.domain.rubric import default_rubric
from rag_core.knowledge.domain.model import VersionStatus
from rag_core.knowledge.infrastructure.memory import InMemoryKnowledgeItemRepository
from rag_core.qa.application.promote import (
    PromoteAnswer,
    PromoteConfig,
    answer_source_id,
)
from rag_core.qa.domain.citations import ParsedCitation, VerifiedCitation
from rag_core.qa.domain.model import QaAnswer, QaStatus
from rag_core.shared_kernel.identifiers import DocumentId
from rag_core.shared_kernel.language import LanguageCode


def _grounded(text: str = "The contract is 2180 million toman [AR-HW-012].") -> QaAnswer:
    return QaAnswer(
        question="What is the contract value?",
        node="N-HW-REP",
        language="en",
        status=QaStatus.ANSWERED,
        text=text,
        citations=[
            VerifiedCitation(
                ParsedCitation("[AR-HW-012]", "AR-HW-012"), True, "document"
            )
        ],
        related=["AR-HW-012"],
    )


def test_promote_config_defaults_to_rubric_accept_total() -> None:
    rubric = default_rubric()
    cfg = PromoteConfig.from_rubric(rubric)
    assert cfg.min_judge_total == rubric.accept_total == 18
    override = PromoteConfig.from_rubric(rubric, override=19)
    assert override.min_judge_total == 19


def test_promote_rejects_ungrounded_and_below_threshold() -> None:
    repo = InMemoryKnowledgeItemRepository()
    svc = PromoteAnswer(repo, config=PromoteConfig.from_rubric())
    weak = QaAnswer("q", "N-CEO", "en", QaStatus.ANSWERED, "no citation", related=[])
    assert svc.promote(weak, judge_total=20, document_id="AR-ANS-001").status == (
        "not_grounded"
    )
    out = svc.promote(_grounded(), judge_total=17, document_id="AR-ANS-001")
    assert out.status == "below_threshold" and "17<18" in out.detail
    assert repo.find_by_document(DocumentId("AR-ANS-001")) is None


def test_promote_stages_draft_with_source_link() -> None:
    repo = InMemoryKnowledgeItemRepository()
    svc = PromoteAnswer(repo, config=PromoteConfig.from_rubric())
    answer = _grounded()
    out = svc.promote(
        answer, judge_total=18, document_id="AR-ANS-001", subject_domain="qa_promoted"
    )
    assert out.status == "promoted"
    assert out.source_answer_id == answer_source_id(answer)
    item = repo.find_by_document(DocumentId("AR-ANS-001"))
    assert item is not None
    draft = item.draft_version(LanguageCode.EN)
    assert draft is not None
    assert draft.status is VersionStatus.DRAFT
    assert draft.change_reason == "promoted_from_qa"
    assert "Promoted from Q&A" in draft.diff_summary
    assert draft.chunks[0].text == answer.text
    again = svc.promote(answer, judge_total=20, document_id="AR-ANS-001")
    assert again.status == "already_exists"
