"""Structured Q&A answer for one node-scoped question."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from rag_core.knowledge.domain.services import Citation
from rag_core.rag.domain.model import Answer, AnswerKind
from rag_core.rag.domain.ports import EscalationRoute
from rag_core.rag.domain.records import SearchFilters, SourceRef
from rag_core.qa.domain.citations import VerifiedCitation
from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.fact_ports import FactValidationReport, FactVerdict
from rag_core.shared_kernel.identifiers import DocumentId
from rag_core.shared_kernel.language import LanguageCode


class QaStatus(StrEnum):
    ANSWERED = "answered"
    INSUFFICIENT_CONTEXT = "insufficient_context"  # evidence retrieved, model refused
    NOT_FOUND_IN_SCOPE = "not_found_in_scope"  # no evidence in the node's scope
    OUT_OF_SCOPE = "out_of_scope"  # evidence exists outside scope -> escalate


REFUSAL_STATUSES = frozenset(
    {QaStatus.INSUFFICIENT_CONTEXT, QaStatus.NOT_FOUND_IN_SCOPE, QaStatus.OUT_OF_SCOPE}
)


@dataclass(frozen=True)
class QaRequest:
    question: str
    node: str
    filters: SearchFilters = field(default_factory=SearchFilters)
    top_k: int | None = None

    def __post_init__(self) -> None:
        if not self.question.strip():
            raise InvariantError("question is required")
        if not self.node.strip():
            raise InvariantError("asking node is required")


@dataclass
class QaAnswer:
    question: str
    node: str
    language: str
    status: QaStatus
    text: str
    citations: list[VerifiedCitation] = field(default_factory=list)
    used_chunks: list[SourceRef] = field(default_factory=list)
    retrieved: list[str] = field(default_factory=list)  # record keys, rank order
    fact_check: FactValidationReport = field(default_factory=FactValidationReport)
    escalation: EscalationRoute | None = None
    raw_model_text: str = ""
    prompt_version: str = ""
    model: str = ""
    timings_s: dict[str, float] = field(default_factory=dict)

    @property
    def valid_citations(self) -> list[VerifiedCitation]:
        return [c for c in self.citations if c.valid]

    @property
    def invalid_citations(self) -> list[VerifiedCitation]:
        return [c for c in self.citations if not c.valid]

    @property
    def grounded(self) -> bool:
        """Answered, with at least one citation and no invalid one."""
        return (
            self.status is QaStatus.ANSWERED
            and bool(self.citations)
            and not self.invalid_citations
        )

    @property
    def fact_flags(self) -> list[str]:
        return [
            f"{r.claim.kind.value}:{r.claim.raw_text}:{r.verdict.value}"
            for r in self.fact_check.results
            if r.verdict in {FactVerdict.FLAGGED, FactVerdict.UNSUPPORTED}
        ]

    def knowledge_citations(self) -> list[Citation]:
        """Valid citations as Phase 3 ``Citation`` value objects."""
        out: list[Citation] = []
        for vc in self.valid_citations:
            for label in vc.block_labels:
                base, _, lang = label.partition("/")
                src = next(
                    (
                        s
                        for s in self.used_chunks
                        if s.label == base and (not lang or s.language == lang)
                    ),
                    None,
                )
                if src is None:
                    continue
                out.append(
                    Citation(
                        DocumentId(src.document_id),
                        src.version,
                        LanguageCode(src.language),
                        chunk_id=f"{src.document_id}#c{src.order:04d}",
                        section=f"§{src.order}",
                        heading_path=src.heading_path,
                    )
                )
        return out

    def to_rag_answer(self) -> Answer:
        """Bridge to the Phase 3 ``Answer`` value object (grounded or abstained)."""
        if self.grounded:
            return Answer(
                AnswerKind.GROUNDED, self.text, tuple(self.knowledge_citations())
            )
        return Answer(
            AnswerKind.ABSTAINED,
            self.status.value if self.status in REFUSAL_STATUSES else "UNVERIFIED",
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "question": self.question,
            "node": self.node,
            "language": self.language,
            "status": self.status.value,
            "grounded": self.grounded,
            "text": self.text,
            "citations": [c.to_dict() for c in self.citations],
            "used_chunks": [s.to_dict() for s in self.used_chunks],
            "retrieved": self.retrieved,
            "fact_check": [
                {
                    "kind": r.claim.kind.value,
                    "value": r.claim.raw_text,
                    "verdict": r.verdict.value,
                    "notes": r.notes,
                }
                for r in self.fact_check.results
            ],
            "fact_flags": self.fact_flags,
            "escalation": None
            if self.escalation is None
            else self.escalation.to_dict(),
            "prompt_version": self.prompt_version,
            "model": self.model,
            "timings_s": {k: round(v, 3) for k, v in self.timings_s.items()},
        }
