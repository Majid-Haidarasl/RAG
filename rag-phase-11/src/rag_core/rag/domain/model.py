"""RetrievalSession aggregate and query/score value objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from rag_core.knowledge.domain.services import Citation
from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.events import DomainEvent
from rag_core.shared_kernel.identifiers import NodeIdentifier
from rag_core.shared_kernel.language import LanguageCode


@dataclass(frozen=True)
class SimilarityScore:
    value: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise InvariantError(f"SimilarityScore must be in [0, 1], got {self.value}")

    def __float__(self) -> float:
        return self.value


@dataclass(frozen=True)
class RetrievalQuery:
    text: str
    node_scope: NodeIdentifier
    language: LanguageCode = LanguageCode.FA
    top_k: int = 5

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise InvariantError("RetrievalQuery text is required")
        if self.top_k < 1:
            raise InvariantError("top_k must be >= 1")


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    document_id: str
    score: SimilarityScore
    text: str = ""
    allowed: bool = True


class AnswerKind(StrEnum):
    GROUNDED = "grounded"
    ABSTAINED = "abstained"


@dataclass(frozen=True)
class Answer:
    kind: AnswerKind
    text: str
    citations: tuple[Citation, ...] = ()

    def __post_init__(self) -> None:
        if self.kind == AnswerKind.GROUNDED and not self.citations:
            raise InvariantError("a grounded answer must carry at least one citation")


@dataclass
class RetrievalSession:
    """Short-lived aggregate for one node-scoped question (UC-04)."""

    query: RetrievalQuery
    hits: list[RetrievedChunk] = field(default_factory=list)
    answer: Answer | None = None
    events: list[DomainEvent] = field(default_factory=list)

    def record_hits(self, hits: list[RetrievedChunk]) -> None:
        if self.answer is not None:
            raise InvariantError("session already closed")
        # Drop chunks the node is not allowed to see (node boundary).
        self.hits = [h for h in hits if h.allowed]

    def ground(self, text: str, citations: list[Citation]) -> Answer:
        if not text.strip():
            raise InvariantError("answer text is required")
        answer = Answer(AnswerKind.GROUNDED, text.strip(), tuple(citations))
        self.answer = answer
        self.events.append(DomainEvent("AnswerGenerated", {"node": str(self.query.node_scope)}))
        return answer

    def abstain(self, reason: str) -> Answer:
        answer = Answer(AnswerKind.ABSTAINED, reason.strip() or "INSUFFICIENT_CONTEXT", ())
        self.answer = answer
        self.events.append(DomainEvent("AnswerAbstained", {"reason": answer.text}))
        return answer
