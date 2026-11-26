"""Node-scoped Q&A use case (UC-04): retrieve → assemble → generate → verify.

Decision flow for a question asked from node X:

1. Hybrid retrieval inside X's scope (+ an out-of-scope probe).
2. No in-scope evidence (best cosine < ``evidence_min_vector``; BM25 floor
   in lexical-only mode):
   * strong evidence outside the scope → ``out_of_scope`` + escalation
     route from Phase 6 (lowest common ancestor of X and the owners);
   * otherwise → ``not_found_in_scope``. The model is not called.
3. Evidence found → prompt with labelled context, local LLM call.
   * The model refuses (``INSUFFICIENT_CONTEXT``) → escalate if outside
     evidence is stronger than inside evidence, else ``insufficient_context``.
   * Otherwise parse and verify citations against the context, then run
     the basic fact check over the cited chunks.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from rag_core.qa.domain.citations import cited_blocks, parse_citations, verify_citations
from rag_core.qa.domain.fact_check import CitedFactValidator
from rag_core.qa.domain.language import question_language
from rag_core.qa.domain.model import QaAnswer, QaRequest, QaStatus
from rag_core.qa.domain.ports import ChatModelPort
from rag_core.qa.domain.prompts import QaPromptSet
from rag_core.rag.domain.context import ContextAssembler
from rag_core.rag.domain.ports import EscalationRoute
from rag_core.rag.domain.retriever import (
    HybridRetriever,
    OutOfScopeEvidence,
    RetrievalResult,
)
from rag_core.shared_kernel.identifiers import DocumentId

RELATED_MAX = 10


def related_document_ids(result: RetrievalResult, *, limit: int = RELATED_MAX) -> list[str]:
    """Unique document ids from retrieval hits, preserving rank order."""
    out: list[str] = []
    seen: set[str] = set()
    for hit in result.hits:
        doc_id = hit.record.document_id
        if doc_id in seen:
            continue
        seen.add(doc_id)
        out.append(doc_id)
        if len(out) >= limit:
            break
    return out


@dataclass(frozen=True)
class QaConfig:
    evidence_min_vector: float = 0.45
    evidence_min_lexical: float = 3.0
    escalate_margin: float = 0.02
    promote_min_judge_total: int | None = None  # None → judge rubric accept_total


class NodeScopedQaService:
    def __init__(
        self,
        retriever: HybridRetriever,
        assembler: ContextAssembler,
        chat: ChatModelPort,
        prompts: QaPromptSet,
        *,
        config: QaConfig | None = None,
        validator: CitedFactValidator | None = None,
        model_name: str = "",
    ) -> None:
        self.retriever = retriever
        self.assembler = assembler
        self.chat = chat
        self.prompts = prompts
        self.config = config or QaConfig()
        self.validator = validator or CitedFactValidator()
        self.model_name = model_name

    # -- evidence ----------------------------------------------------------------
    def _strength(self, vector: float | None, lexical: float | None) -> float | None:
        if self.retriever.mode == "hybrid":
            return vector
        return lexical

    def _threshold(self) -> float:
        return (
            self.config.evidence_min_vector
            if self.retriever.mode == "hybrid"
            else self.config.evidence_min_lexical
        )

    def inside_strength(self, result: RetrievalResult) -> float | None:
        return self._strength(result.best_vector, result.best_lexical)

    def strong_outside(self, result: RetrievalResult) -> list[OutOfScopeEvidence]:
        th = self._threshold()
        return [
            e
            for e in result.out_of_scope
            if (s := self._strength(e.vector_score, e.lexical_score)) is not None
            and s >= th
        ]

    def _escalation(
        self, node: str, evidence: list[OutOfScopeEvidence]
    ) -> EscalationRoute | None:
        scope = self.retriever.scope
        owners = list(dict.fromkeys(e.owner_node for e in evidence if e.owner_node))
        if scope is None or not owners:
            return None
        return scope.route(node, owners)

    # -- use case ------------------------------------------------------------------
    def ask(self, request: QaRequest) -> QaAnswer:
        t0 = time.perf_counter()
        lang = question_language(request.question)
        result = self.retriever.retrieve(
            request.question, request.node, request.filters, top_k=request.top_k
        )
        timings = {"retrieval": result.timings_s.get("total", 0.0)}
        answer = QaAnswer(
            request.question,
            request.node,
            lang,
            QaStatus.NOT_FOUND_IN_SCOPE,
            "",
            retrieved=[h.key for h in result.hits],
            related=related_document_ids(result),
            prompt_version=self.prompts.version,
            model=self.model_name,
            timings_s=timings,
        )
        if result.best_vector is not None:
            answer.confidence = float(result.best_vector)
        inside = self.inside_strength(result)
        has_evidence = (
            bool(result.hits) and inside is not None and inside >= self._threshold()
        )
        outside = self.strong_outside(result)
        if not has_evidence:
            self._refuse(answer, outside, inside)
            timings["total"] = time.perf_counter() - t0
            return answer

        context = self.assembler.assemble(result.hits)
        answer.used_chunks = [b.source for b in context.blocks]
        system, user = self.prompts.render(
            question=request.question,
            context=context.text,
            language=lang,
            node=request.node,
        )
        t = time.perf_counter()
        reply = self.chat.generate(system, user)
        timings["generation"] = time.perf_counter() - t
        answer.raw_model_text = reply.text
        if self.prompts.is_refusal(reply.text):
            stronger = [
                e
                for e in outside
                if (s := self._strength(e.vector_score, e.lexical_score)) is not None
                and s >= (inside or 0.0) + self.config.escalate_margin
            ]
            if stronger:
                self._refuse(answer, stronger, inside)
            else:
                answer.status = QaStatus.INSUFFICIENT_CONTEXT
                answer.text = self.prompts.message(
                    "insufficient", lang, node=request.node
                )
            timings["total"] = time.perf_counter() - t0
            return answer

        answer.status = QaStatus.ANSWERED
        answer.text = reply.text.strip()
        answer.citations = verify_citations(parse_citations(answer.text), context)
        cited = cited_blocks(answer.citations, context)
        answer.fact_check = self.validator.validate(
            answer.text,
            [b.hit.record.text for b in cited],
            source_document_ids=[DocumentId(b.hit.record.document_id) for b in cited],
            context_texts=[b.hit.record.text for b in context.blocks],
        )
        timings["total"] = time.perf_counter() - t0
        return answer

    def _refuse(
        self, answer: QaAnswer, outside: list[OutOfScopeEvidence], inside: float | None
    ) -> None:
        stronger = [
            e
            for e in outside
            if inside is None
            or (
                (s := self._strength(e.vector_score, e.lexical_score)) is not None
                and s >= inside + self.config.escalate_margin
            )
            or inside < self._threshold()
        ]
        route = self._escalation(answer.node, stronger) if stronger else None
        if route is not None and route.action == "escalate":
            answer.status = QaStatus.OUT_OF_SCOPE
            answer.escalation = route
            answer.text = self.prompts.message(
                "out_of_scope",
                answer.language,
                node=answer.node,
                target=route.target,
                reason=route.reason,
            )
        else:
            answer.status = QaStatus.NOT_FOUND_IN_SCOPE
            answer.text = self.prompts.message(
                "not_found", answer.language, node=answer.node
            )
