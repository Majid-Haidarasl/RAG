"""Promote a judged QaAnswer into a reviewed (draft) KnowledgeItem."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from rag_core.judging.domain.rubric import Rubric, default_rubric
from rag_core.knowledge.domain.model import (
    KnowledgeChunk,
    KnowledgeItem,
    KnowledgeScope,
    VersionTag,
)
from rag_core.knowledge.domain.repositories import KnowledgeItemRepository
from rag_core.qa.domain.model import QaAnswer
from rag_core.shared_kernel.confidentiality import Confidentiality
from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.events import DomainEvent
from rag_core.shared_kernel.identifiers import (
    DocumentId,
    KnowledgeItemId,
    NodeIdentifier,
)
from rag_core.shared_kernel.language import LanguageCode


@dataclass(frozen=True)
class PromoteConfig:
    """``min_judge_total`` defaults to the judge rubric ``accept_total``."""

    min_judge_total: int = 18
    out_of: int = 20

    @classmethod
    def from_rubric(
        cls, rubric: Rubric | None = None, *, override: int | None = None
    ) -> PromoteConfig:
        r = rubric or default_rubric()
        total = r.accept_total if override is None else override
        if not 1 <= total <= r.out_of:
            raise InvariantError(
                f"promote_min_judge_total must be within 1..{r.out_of}, got {total}"
            )
        return cls(min_judge_total=total, out_of=r.out_of)


@dataclass(frozen=True)
class PromoteOutcome:
    status: str  # promoted | below_threshold | not_grounded | already_exists
    document_id: str = ""
    version: str = ""
    source_answer_id: str = ""
    detail: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "document_id": self.document_id,
            "version": self.version,
            "source_answer_id": self.source_answer_id,
            "detail": self.detail,
        }


def answer_source_id(answer: QaAnswer) -> str:
    digest = sha256(
        f"{answer.node}\n{answer.question}\n{answer.text}".encode()
    ).hexdigest()
    return f"qa:{digest[:16]}"


def _chunk_answer(answer: QaAnswer, document_id: str) -> list[KnowledgeChunk]:
    text = answer.text.strip()
    if not text:
        raise InvariantError("cannot promote an empty answer")
    return [
        KnowledgeChunk(
            chunk_id=f"{document_id}#c0001",
            order=1,
            text=text,
            heading_path="promoted_answer",
            section="answer",
        )
    ]


class PromoteAnswer:
    """Turn a grounded, judge-accepted QaAnswer into a draft KnowledgeItem."""

    def __init__(
        self,
        repository: KnowledgeItemRepository,
        *,
        config: PromoteConfig | None = None,
    ) -> None:
        self.repository = repository
        self.config = config or PromoteConfig.from_rubric()

    def promote(
        self,
        answer: QaAnswer,
        *,
        judge_total: int,
        document_id: str,
        owning_node: str | None = None,
        confidentiality: str = "internal",
        subject_domain: str = "promoted_answer",
        version: str = "1.0",
    ) -> PromoteOutcome:
        source_id = answer_source_id(answer)
        if not answer.grounded:
            return PromoteOutcome(
                "not_grounded", source_answer_id=source_id, detail="answer is not grounded"
            )
        if judge_total < self.config.min_judge_total:
            return PromoteOutcome(
                "below_threshold",
                source_answer_id=source_id,
                detail=(
                    f"judge total {judge_total}<{self.config.min_judge_total}"
                    f"/{self.config.out_of}"
                ),
            )
        doc = DocumentId(document_id)
        if self.repository.find_by_document(doc) is not None:
            return PromoteOutcome(
                "already_exists",
                document_id=str(doc),
                source_answer_id=source_id,
                detail="knowledge item already registered for this id",
            )
        lang = LanguageCode(answer.language)
        node = NodeIdentifier(owning_node or answer.node)
        conf = Confidentiality(confidentiality)
        tag = VersionTag.parse(version)
        chunks = _chunk_answer(answer, str(doc))
        item = KnowledgeItem(
            item_id=KnowledgeItemId(str(doc)),
            document_id=doc,
            owning_node=node,
            confidentiality=conf,
            scope=KnowledgeScope(subject_domain, conf),
        )
        item.events.append(
            DomainEvent("KnowledgeItemRegistered", {"document_id": str(doc)})
        )
        draft = item.stage_draft(
            tag,
            lang,
            chunks,
            change_reason="promoted_from_qa",
            diff_summary=f"Promoted from Q&A ({source_id}): {answer.question[:120]}",
        )
        # Provenance for metadata consumers (not part of the aggregate schema).
        item.events.append(
            DomainEvent(
                "AnswerPromoted",
                {
                    "document_id": str(doc),
                    "source_answer_id": source_id,
                    "judge_total": judge_total,
                    "node": answer.node,
                },
            )
        )
        self.repository.save(item)
        return PromoteOutcome(
            "promoted",
            document_id=str(doc),
            version=str(draft.tag),
            source_answer_id=source_id,
            detail="draft knowledge item staged from judged answer",
        )
