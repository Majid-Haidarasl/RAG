"""Scoring of the fixed sample questions (live demo and offline dry run)."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from statistics import mean

from rag_core.knowledge.domain.fingerprint import tokens as normalized_tokens
from rag_core.qa.domain.model import QaAnswer, QaStatus
from rag_core.rag.domain.retriever import RetrievalResult
from rag_core.shared_kernel.numerals import normalize_digits
from rag_core.shared_kernel.persian import normalize_yeh_kaf

EXPECTED_STATUSES = {"answered", "out_of_scope", "not_found"}


@dataclass(frozen=True)
class SampleQuestion:
    id: str
    node: str
    language: str
    question: str
    expected_status: str
    expected_docs: tuple[str, ...] = ()
    expected_outside_docs: tuple[str, ...] = ()
    expected_escalation: str = ""
    expected_facts: tuple[tuple[str, ...], ...] = ()
    case: str = ""

    def __post_init__(self) -> None:
        if self.expected_status not in EXPECTED_STATUSES:
            raise ValueError(f"{self.id}: unknown expected_status {self.expected_status}")
        if self.language not in {"fa", "en"}:
            raise ValueError(f"{self.id}: language must be fa or en")


def load_samples(path: Path) -> list[SampleQuestion]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out: list[SampleQuestion] = []
    for q in data["questions"]:
        out.append(
            SampleQuestion(
                id=q["id"], node=q["node"], language=q["language"], question=q["question"],
                expected_status=q["expected_status"],
                expected_docs=tuple(q.get("expected_docs", [])),
                expected_outside_docs=tuple(q.get("expected_outside_docs", [])),
                expected_escalation=q.get("expected_escalation", ""),
                expected_facts=tuple(tuple(g) for g in q.get("expected_facts", [])),
                case=q.get("case", ""),
            )
        )
    ids = [s.id for s in out]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate sample ids")
    return out


def hit_at_k(result: RetrievalResult, expected: tuple[str, ...], k: int = 5) -> bool | None:
    if not expected:
        return None
    return any(h.record.document_id in expected for h in result.hits[:k])


def reciprocal_rank(result: RetrievalResult, expected: tuple[str, ...]) -> float | None:
    if not expected:
        return None
    for i, hit in enumerate(result.hits, start=1):
        if hit.record.document_id in expected:
            return 1.0 / i
    return 0.0


def _norm(text: str) -> str:
    return " ".join(normalized_tokens(normalize_digits(normalize_yeh_kaf(text))))


def facts_found(answer_text: str, groups: tuple[tuple[str, ...], ...]) -> tuple[int, int]:
    """(groups with at least one alternative in the answer, total groups)."""
    text = f" {_norm(answer_text)} "
    hits = 0
    for group in groups:
        if any(f" {_norm(alt)} " in text for alt in group):
            hits += 1
    return hits, len(groups)


def status_ok(sample: SampleQuestion, answer: QaAnswer) -> bool:
    if sample.expected_status == "answered":
        return answer.status is QaStatus.ANSWERED
    if sample.expected_status == "out_of_scope":
        if answer.status is not QaStatus.OUT_OF_SCOPE:
            return False
        return not sample.expected_escalation or (
            answer.escalation is not None and answer.escalation.target == sample.expected_escalation
        )
    return answer.status in {QaStatus.NOT_FOUND_IN_SCOPE, QaStatus.INSUFFICIENT_CONTEXT}


def outside_detected(sample: SampleQuestion, result: RetrievalResult) -> bool | None:
    if not sample.expected_outside_docs:
        return None
    return any(e.document_id in sample.expected_outside_docs for e in result.out_of_scope)


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))]


@dataclass
class RetrievalMetrics:
    hit_at_5: float | None = None
    mrr: float | None = None
    scored: int = 0
    outside_detected: str = "0/0"

    def to_dict(self) -> dict[str, object]:
        return {"hit_at_5": self.hit_at_5, "mrr": self.mrr, "scored": self.scored,
                "outside_detected": self.outside_detected}


def retrieval_metrics(rows: list[tuple[SampleQuestion, RetrievalResult]]) -> RetrievalMetrics:
    hits = [h for s, r in rows if (h := hit_at_k(r, s.expected_docs)) is not None]
    rrs = [x for s, r in rows if (x := reciprocal_rank(r, s.expected_docs)) is not None]
    outs = [o for s, r in rows if (o := outside_detected(s, r)) is not None]
    return RetrievalMetrics(
        hit_at_5=round(sum(hits) / len(hits), 3) if hits else None,
        mrr=round(mean(rrs), 3) if rrs else None,
        scored=len(hits),
        outside_detected=f"{sum(outs)}/{len(outs)}",
    )


@dataclass
class QaMetrics:
    questions: int = 0
    status_ok: int = 0
    answered: int = 0
    grounded: int = 0
    citations_total: int = 0
    citations_valid: int = 0
    scope_handling_ok: int = 0
    scope_handling_total: int = 0
    facts_hit: int = 0
    facts_total: int = 0
    fact_flags: int = 0
    generation_avg_s: float = 0.0
    generation_p95_s: float = 0.0
    retrieval_avg_s: float = 0.0
    per_question: list[dict[str, object]] = field(default_factory=list)

    @property
    def citation_validity(self) -> float | None:
        return round(self.citations_valid / self.citations_total, 3) if self.citations_total else None

    def to_dict(self) -> dict[str, object]:
        return {
            "questions": self.questions, "status_ok": self.status_ok, "answered": self.answered,
            "grounded": self.grounded, "citations_total": self.citations_total,
            "citations_valid": self.citations_valid, "citation_validity": self.citation_validity,
            "scope_handling": f"{self.scope_handling_ok}/{self.scope_handling_total}",
            "facts": f"{self.facts_hit}/{self.facts_total}", "fact_flags": self.fact_flags,
            "generation_avg_s": round(self.generation_avg_s, 2), "generation_p95_s": round(self.generation_p95_s, 2),
            "retrieval_avg_s": round(self.retrieval_avg_s, 3),
        }


def qa_metrics(rows: list[tuple[SampleQuestion, QaAnswer]]) -> QaMetrics:
    m = QaMetrics(questions=len(rows))
    gen: list[float] = []
    ret: list[float] = []
    for sample, ans in rows:
        ok = status_ok(sample, ans)
        m.status_ok += ok
        if sample.expected_status in {"out_of_scope", "not_found"}:
            m.scope_handling_total += 1
            m.scope_handling_ok += ok
        if ans.status is QaStatus.ANSWERED:
            m.answered += 1
            m.grounded += ans.grounded
            m.citations_total += len(ans.citations)
            m.citations_valid += len(ans.valid_citations)
            m.fact_flags += len(ans.fact_flags)
        fh, ft = facts_found(ans.text, sample.expected_facts) if ans.status is QaStatus.ANSWERED else (0, len(sample.expected_facts))
        m.facts_hit += fh
        m.facts_total += ft
        if "generation" in ans.timings_s:
            gen.append(ans.timings_s["generation"])
        ret.append(ans.timings_s.get("retrieval", 0.0))
        m.per_question.append({"id": sample.id, "status": ans.status.value, "status_ok": ok,
                               "citations": f"{len(ans.valid_citations)}/{len(ans.citations)}",
                               "facts": f"{fh}/{ft}", "fact_flags": len(ans.fact_flags),
                               "escalation": ans.escalation.target if ans.escalation else ""})
    m.generation_avg_s = mean(gen) if gen else 0.0
    m.generation_p95_s = _p95(gen)
    m.retrieval_avg_s = mean(ret) if ret else 0.0
    return m
