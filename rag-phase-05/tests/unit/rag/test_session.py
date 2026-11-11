import pytest

from rag_core.knowledge.domain.services import Citation
from rag_core.rag.domain.model import (
    AnswerKind,
    RetrievalQuery,
    RetrievalSession,
    RetrievedChunk,
    SimilarityScore,
)
from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.identifiers import DocumentId, NodeIdentifier
from rag_core.shared_kernel.language import LanguageCode

pytestmark = pytest.mark.rag


def test_grounded_answer_requires_citation() -> None:
    session = RetrievalSession(RetrievalQuery("زمان پاسخ اولویت ۱؟", NodeIdentifier("N-SW-SUP"), LanguageCode.FA))
    session.record_hits(
        [RetrievedChunk("c1", "AR-SW-022", SimilarityScore(0.91), "۳۰ دقیقه", allowed=True)]
    )
    with pytest.raises(InvariantError, match="citation"):
        session.ground("۳۰ دقیقه", [])
    answer = session.ground(
        "زمان پاسخ رویداد اولویت ۱ برابر ۳۰ دقیقه است.",
        [Citation(DocumentId("AR-SW-022"), "1.0", LanguageCode.FA, section="P1")],
    )
    assert answer.kind is AnswerKind.GROUNDED


def test_session_drops_disallowed_chunks_and_can_abstain() -> None:
    session = RetrievalSession(RetrievalQuery("حقوق پرسنل؟", NodeIdentifier("N-HW-SAL")))
    session.record_hits(
        [
            RetrievedChunk("hr", "AR-EXE-023", SimilarityScore(0.8), "salary", allowed=False),
        ]
    )
    assert session.hits == []
    answer = session.abstain("INSUFFICIENT_CONTEXT")
    assert answer.kind is AnswerKind.ABSTAINED
    assert any(e.name == "AnswerAbstained" for e in session.events)


def test_similarity_score_bounds() -> None:
    with pytest.raises(InvariantError):
        SimilarityScore(1.2)
