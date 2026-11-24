"""Evaluation metrics (stdlib only).

* ranking — hit@k, reciprocal rank and MRR over the ranked document ids of a
  retrieval; *context facts*: the share of expected fact groups that are in the
  assembled context (what the model could see). A missed fact with the fact in
  the context is a generation problem; without it, a retrieval problem.
* agreement — accept/reject decisions against gold labels: accuracy, false
  accepts (leniency), false rejects and Cohen's kappa.
* latency — mean and p95 of seconds.
* detail — answer length rule per detail level (short / list / refusal).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
import math
import re

SENTENCE_RE = re.compile(r"(?<=[.!?؟])\s+|\n+")
DETAIL_MAX_SENTENCES = {"short": 3, "list": 6, "refusal": 2}


def rounded(value: float | None, digits: int = 3) -> float | None:
    return None if value is None else round(value, digits)


def mean(values: Iterable[float]) -> float | None:
    rows = list(values)
    return round(sum(rows) / len(rows), 3) if rows else None


def p95(values: Iterable[float]) -> float | None:
    rows = sorted(values)
    if not rows:
        return None
    return round(rows[min(len(rows) - 1, int(math.ceil(0.95 * len(rows))) - 1)], 3)


def unique(seq: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(seq))


def hit_at(ranked: Sequence[str], expected: Iterable[str], k: int) -> bool | None:
    wanted = set(expected)
    if not wanted:
        return None
    return any(d in wanted for d in unique(ranked)[:k])


def reciprocal_rank(ranked: Sequence[str], expected: Iterable[str]) -> float | None:
    wanted = set(expected)
    if not wanted:
        return None
    for i, doc in enumerate(unique(ranked), 1):
        if doc in wanted:
            return 1.0 / i
    return 0.0


@dataclass(frozen=True)
class RankingRow:
    item_id: str
    ranked: tuple[str, ...]
    expected: tuple[str, ...]
    context_facts: tuple[int, int] = (0, 0)
    seconds: float = 0.0
    scope_violations: int = 0

    @property
    def first_rank(self) -> int | None:
        wanted = set(self.expected)
        for i, doc in enumerate(unique(self.ranked), 1):
            if doc in wanted:
                return i
        return None

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.item_id,
            "top_docs": list(unique(self.ranked)[:5]),
            "expected": list(self.expected),
            "rank": self.first_rank,
            "context_facts": f"{self.context_facts[0]}/{self.context_facts[1]}",
            "seconds": round(self.seconds, 4),
            "scope_violations": self.scope_violations,
        }


@dataclass
class RankingSummary:
    n: int = 0
    hit_at_1: float | None = None
    hit_at_3: float | None = None
    hit_at_5: float | None = None
    mrr: float | None = None
    context_facts_hit: int = 0
    context_facts_total: int = 0
    full_context: int = 0
    scope_violations: int = 0
    seconds_avg: float | None = None
    misses: list[str] = field(default_factory=list)
    rows: list[RankingRow] = field(default_factory=list)

    @property
    def context_facts(self) -> float | None:
        return (
            rounded(self.context_facts_hit / self.context_facts_total)
            if self.context_facts_total
            else None
        )

    def metric(self, name: str) -> float | None:
        return {
            "hit_at_1": self.hit_at_1,
            "hit_at_3": self.hit_at_3,
            "hit_at_5": self.hit_at_5,
            "mrr": self.mrr,
            "context_facts": self.context_facts,
        }.get(name)

    def to_dict(self) -> dict[str, object]:
        return {
            "n": self.n,
            "hit_at_1": self.hit_at_1,
            "hit_at_3": self.hit_at_3,
            "hit_at_5": self.hit_at_5,
            "mrr": self.mrr,
            "context_facts": self.context_facts,
            "context_facts_count": f"{self.context_facts_hit}/{self.context_facts_total}",
            "full_context": self.full_context,
            "scope_violations": self.scope_violations,
            "seconds_avg": self.seconds_avg,
            "misses": list(self.misses),
            "rows": [r.to_dict() for r in self.rows],
        }


def summarize_ranking(rows: Iterable[RankingRow]) -> RankingSummary:
    rows = [r for r in rows if r.expected]
    out = RankingSummary(n=len(rows), rows=rows)
    if not rows:
        return out
    for k in (1, 3, 5):
        hits = [bool(hit_at(r.ranked, r.expected, k)) for r in rows]
        setattr(out, f"hit_at_{k}", rounded(sum(hits) / len(hits)))
    out.mrr = mean(reciprocal_rank(r.ranked, r.expected) or 0.0 for r in rows)
    out.context_facts_hit = sum(r.context_facts[0] for r in rows)
    out.context_facts_total = sum(r.context_facts[1] for r in rows)
    out.full_context = sum(
        1
        for r in rows
        if r.context_facts[1] and r.context_facts[0] == r.context_facts[1]
    )
    out.scope_violations = sum(r.scope_violations for r in rows)
    out.seconds_avg = mean(r.seconds for r in rows)
    out.misses = [
        r.item_id
        for r in rows
        if r.context_facts[0] < r.context_facts[1]
        or not hit_at(r.ranked, r.expected, 5)
    ]
    return out


@dataclass(frozen=True)
class Agreement:
    n: int
    agree: int
    accuracy: float | None
    kappa: float | None
    true_accepts: int
    false_accepts: int
    true_rejects: int
    false_rejects: int

    @property
    def leniency(self) -> float | None:
        """Share of gold rejects that were accepted (lower is stricter)."""
        negatives = self.false_accepts + self.true_rejects
        return rounded(self.false_accepts / negatives) if negatives else None

    def to_dict(self) -> dict[str, object]:
        return {
            "n": self.n,
            "agree": self.agree,
            "accuracy": self.accuracy,
            "kappa": self.kappa,
            "true_accepts": self.true_accepts,
            "false_accepts": self.false_accepts,
            "true_rejects": self.true_rejects,
            "false_rejects": self.false_rejects,
            "leniency": self.leniency,
        }


def binary_agreement(pairs: Iterable[tuple[bool, bool]]) -> Agreement:
    """``pairs`` = (predicted accept, gold accept). Cohen's kappa is ``None`` when it is undefined."""
    rows = list(pairs)
    n = len(rows)
    ta = sum(1 for p, g in rows if p and g)
    fa = sum(1 for p, g in rows if p and not g)
    tr = sum(1 for p, g in rows if not p and not g)
    fr = sum(1 for p, g in rows if not p and g)
    if not n:
        return Agreement(0, 0, None, None, 0, 0, 0, 0)
    p_o = (ta + tr) / n
    p_pred = (ta + fa) / n
    p_gold = (ta + fr) / n
    p_e = p_pred * p_gold + (1 - p_pred) * (1 - p_gold)
    kappa = rounded((p_o - p_e) / (1 - p_e)) if 1 - p_e > 1e-9 else None
    return Agreement(n, ta + tr, rounded(p_o), kappa, ta, fa, tr, fr)


def sentences(text: str) -> list[str]:
    return [s for s in (p.strip() for p in SENTENCE_RE.split(text or "")) if s]


def detail_ok(text: str, detail: str) -> bool:
    """The answer respects the sentence limit of its detail level."""
    limit = DETAIL_MAX_SENTENCES.get(detail, DETAIL_MAX_SENTENCES["list"])
    return 0 < len(sentences(text)) <= limit


def share(hit: int, total: int) -> float | None:
    return rounded(hit / total) if total else None
