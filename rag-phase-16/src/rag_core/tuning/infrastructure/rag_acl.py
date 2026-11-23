"""Anti-corruption layer to the retrieval and Q&A contexts (Phase 8).

Turns gold items into Phase 8 sample questions, retrieval variants into
``RetrievalConfig`` / ``ContextAssembler`` objects, and checks the gold set
against the real corpus (quotes, numbers, ids) and the Phase 6 scope.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace
import time
from typing import Any

from rag_core.knowledge.domain.fingerprint import tokens as normalized_tokens
from rag_core.qa.application.evaluation import SampleQuestion, facts_found
from rag_core.qa.domain.fact_check import CitedFactValidator, flagged
from rag_core.rag.domain.context import ContextAssembler
from rag_core.rag.domain.ports import ScopePort
from rag_core.rag.domain.records import ChunkRecord
from rag_core.rag.domain.retriever import RetrievalConfig, RetrievalResult
from rag_core.shared_kernel.numerals import normalize_digits
from rag_core.shared_kernel.persian import normalize_yeh_kaf
from rag_core.tuning.domain.gold import GoldItem
from rag_core.tuning.domain.metrics import RankingRow
from rag_core.tuning.infrastructure.config import RetrievalVariant


def to_sample(item: GoldItem) -> SampleQuestion:
    return SampleQuestion(
        id=item.id, node=item.node, language=item.language, question=item.question,
        expected_status=item.expected_status, expected_docs=item.expected_docs,
        expected_outside_docs=item.expected_outside_docs, expected_escalation=item.expected_escalation,
        expected_facts=item.expected_facts, case=item.pair)


def retrieval_config(variant: RetrievalVariant, base: RetrievalConfig | None = None) -> RetrievalConfig:
    return replace(base or RetrievalConfig(), top_k=variant.top_k, candidate_k=variant.candidate_k,
                   lexical_weight=variant.lexical_weight, vector_weight=variant.vector_weight)


def assembler(variant: RetrievalVariant, max_block_tokens: int = 900) -> ContextAssembler:
    return ContextAssembler(variant.budget_tokens, max_block_tokens)


def norm_text(text: str) -> str:
    return " ".join(normalized_tokens(normalize_digits(normalize_yeh_kaf(text or ""))))


def ranking_row(item: GoldItem, result: RetrievalResult, context_text: str, seconds: float,
                visible: frozenset[str] | None = None) -> RankingRow:
    ranked = tuple(result.document_ids())
    violations = 0 if visible is None else sum(1 for d in ranked if d not in visible)
    found = facts_found(context_text, item.expected_facts) if item.expected_facts else (0, 0)
    return RankingRow(item.id, ranked, item.expected_docs, found, seconds, violations)


Retrieve = Callable[[GoldItem], tuple[RetrievalResult, str]]


def rank_items(items: Iterable[GoldItem], retrieve: Retrieve, scope: ScopePort | None = None) -> list[RankingRow]:
    """One ranking row per answered item: ``retrieve`` returns the result and the assembled context text."""
    rows: list[RankingRow] = []
    for item in items:
        if not item.answered:
            continue
        t = time.perf_counter()
        result, text = retrieve(item)
        seconds = time.perf_counter() - t
        visible = scope.visible_documents(item.node) if scope is not None else None
        rows.append(ranking_row(item, result, text, seconds, visible))
    return rows


# ---- gold set against the corpus -------------------------------------------------------
@dataclass(frozen=True)
class GroundingProblem:
    item_id: str
    code: str      # quote_not_in_corpus | fact_not_in_quote | unsupported_claim | unknown_document
    detail: str = ""

    def __str__(self) -> str:
        return f"{self.item_id}:{self.code}" + (f" ({self.detail})" if self.detail else "")


def document_texts(records: Iterable[ChunkRecord]) -> dict[tuple[str, str], list[str]]:
    """(document id, language) -> normalized active chunk texts in reading order."""
    by: dict[tuple[str, str], list[ChunkRecord]] = {}
    for r in records:
        if r.is_active:
            by.setdefault((r.document_id, r.language), []).append(r)
    return {k: [norm_text(r.text) for r in sorted(v, key=lambda r: r.order)] for k, v in by.items()}


def quote_in(quote: str, chunks: Sequence[str]) -> bool:
    q = norm_text(quote)
    if not q:
        return False
    return any(q in c for c in chunks) or q in " ".join(chunks)


def gold_grounding(items: Iterable[GoldItem], docs: dict[tuple[str, str], list[str]],
                   validator: CitedFactValidator | None = None) -> list[GroundingProblem]:
    """Every quote is in its document, every fact is in the quotes, the reference adds no number or id."""
    validator = validator or CitedFactValidator()
    out: list[GroundingProblem] = []
    for item in items:
        for i, e in enumerate(item.evidence, 1):
            chunks = docs.get((e.document_id, e.language))
            if chunks is None:
                out.append(GroundingProblem(item.id, "unknown_document", f"{e.document_id}/{e.language}"))
            elif not quote_in(e.quote, chunks):
                out.append(GroundingProblem(item.id, "quote_not_in_corpus", f"§{i}"))
        if not item.answered:
            continue
        for group in item.expected_facts:
            if facts_found(item.quote_text, (group,))[0] == 0:
                out.append(GroundingProblem(item.id, "fact_not_in_quote", group[0]))
        for text, which in ((item.reference_answer, "reference"), (item.partial_answer, "partial")):
            if not text.strip():
                continue
            report = validator.validate(text, [e.quote for e in item.evidence],
                                        source_document_ids=list(item.expected_docs))
            for r in flagged(report):
                out.append(GroundingProblem(item.id, "unsupported_claim", f"{which}: {r.claim.raw_text}"))
    return out


def scope_problems(items: Iterable[GoldItem], scope: ScopePort) -> list[str]:
    """Answered items see their documents; out-of-scope items do not, and the escalation matches the route."""
    out: list[str] = []
    for item in items:
        if not scope.exists(item.node):
            out.append(f"{item.id}:unknown_node")
            continue
        visible = scope.visible_documents(item.node)
        if item.answered:
            out += [f"{item.id}:not_visible:{d}" for d in item.expected_docs if d not in visible]
        if item.expected_status == "out_of_scope":
            out += [f"{item.id}:visible_outside:{d}" for d in item.expected_outside_docs if d in visible]
            owners = [o for o in (scope.owner_of(d) for d in item.expected_outside_docs) if o]
            if not owners:
                out.append(f"{item.id}:no_owner")
            else:
                route = scope.route(item.node, owners)
                if route.action != "escalate" or route.target != item.expected_escalation:
                    out.append(f"{item.id}:route:{route.action}->{route.target}")
    return out


class CachingEmbedder:
    """Embedding port that remembers query vectors, so four retrieval variants embed each question once."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.cache: dict[str, list[float]] = {}
        self.calls = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        todo = [t for t in dict.fromkeys(texts) if t not in self.cache]
        if todo:
            self.calls += 1
            for text, vec in zip(todo, self.inner.embed(todo)):
                self.cache[text] = vec
        return [self.cache[t] for t in texts]

    def __getattr__(self, name: str) -> Any:
        if name == "inner":
            raise AttributeError(name)
        return getattr(self.inner, name)
