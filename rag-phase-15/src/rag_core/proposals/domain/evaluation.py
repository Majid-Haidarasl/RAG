"""Weighted evaluation of registered proposals against the RFP criteria.

``weighted = Σ score(criterion) × weight(criterion)`` with the blueprint
weights (they sum to 1), computed with ``Decimal`` and rounded half-up to one
decimal (the Phase 1 ``compute_weighted_score``). Every contribution is kept,
so the score is transparent: A = 82 × 0.6 + 74 × 0.4 = 49.2 + 29.6 = 78.8.
A proposal that misses a required response section is not compliant and
cannot win. The recorded decision must name the top compliant proposal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from rag_core.proposals.domain.model import ProposalRegistry
from rag_core.rfp.domain.blueprint import Blueprint
from rag_core.rfp.domain.model import TWOPLACES, CriterionWeight, compute_weighted_score
from rag_core.shared_kernel.errors import InvariantError


def q(value: Decimal) -> Decimal:
    return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def text(value: Decimal | int | None) -> str:
    if value is None:
        return ""
    d = Decimal(value)
    return str(d.quantize(Decimal(1))) if d == d.to_integral_value() else str(d.normalize())


@dataclass(frozen=True)
class ScoreLine:
    criterion_id: str
    weight: Decimal
    score: Decimal
    contribution: Decimal

    def to_dict(self) -> dict[str, str]:
        return {"criterion": self.criterion_id, "weight": text(self.weight), "score": text(self.score),
                "contribution": str(self.contribution)}


@dataclass(frozen=True)
class ProposalScore:
    proposal_id: str
    lines: tuple[ScoreLine, ...]
    weighted: Decimal | None
    published: Decimal | None
    price: Decimal
    duration: int
    missing_sections: tuple[str, ...] = ()
    rank: int = 0
    error: str = ""

    @property
    def compliant(self) -> bool:
        return not self.missing_sections and self.weighted is not None

    @property
    def matches_published(self) -> bool:
        return self.published is None or (self.weighted is not None and self.weighted == self.published)

    def line(self, criterion_id: str) -> ScoreLine | None:
        return next((x for x in self.lines if x.criterion_id == criterion_id), None)

    def to_dict(self) -> dict[str, object]:
        return {"proposal": self.proposal_id, "lines": [x.to_dict() for x in self.lines],
                "weighted": str(self.weighted) if self.weighted is not None else None,
                "published": str(self.published) if self.published is not None else None,
                "matches_published": self.matches_published, "price_mtoman": text(self.price),
                "duration_weeks": self.duration, "compliant": self.compliant,
                "missing_sections": list(self.missing_sections), "rank": self.rank, "error": self.error}


@dataclass
class Evaluation:
    rfp_id: str
    scores: list[ProposalScore] = field(default_factory=list)
    selected: str = ""

    def get(self, proposal_id: str) -> ProposalScore | None:
        return next((s for s in self.scores if s.proposal_id == proposal_id), None)

    @property
    def ranked(self) -> list[ProposalScore]:
        return sorted((s for s in self.scores if s.rank), key=lambda s: s.rank)

    @property
    def winner(self) -> ProposalScore | None:
        return next((s for s in self.ranked if s.compliant), None)

    @property
    def runner_up(self) -> ProposalScore | None:
        w = self.winner
        return next((s for s in self.ranked if w is not None and s.proposal_id != w.proposal_id), None)

    @property
    def margin(self) -> Decimal | None:
        w, r = self.winner, self.runner_up
        if w is None or r is None or w.weighted is None or r.weighted is None:
            return None
        return q(w.weighted - r.weighted)

    @property
    def cheapest(self) -> ProposalScore | None:
        return min(self.scores, key=lambda s: (s.price, s.proposal_id), default=None)

    @property
    def fastest(self) -> ProposalScore | None:
        return min(self.scores, key=lambda s: (s.duration, s.proposal_id), default=None)

    @property
    def price_gap(self) -> Decimal | None:
        w, c = self.winner, self.cheapest
        return None if w is None or c is None else w.price - c.price

    @property
    def duration_gap(self) -> int | None:
        w, f = self.winner, self.fastest
        return None if w is None or f is None else w.duration - f.duration

    @property
    def published_match(self) -> int:
        return sum(1 for s in self.scores if s.published is not None and s.matches_published)

    @property
    def published_total(self) -> int:
        return sum(1 for s in self.scores if s.published is not None)

    @property
    def decision_consistent(self) -> bool:
        w = self.winner
        return bool(self.selected) and w is not None and w.proposal_id == self.selected

    def to_dict(self) -> dict[str, object]:
        w, r, c, f = self.winner, self.runner_up, self.cheapest, self.fastest
        return {"rfp_id": self.rfp_id, "scores": [s.to_dict() for s in self.scores],
                "winner": w.proposal_id if w else None, "runner_up": r.proposal_id if r else None,
                "margin": str(self.margin) if self.margin is not None else None,
                "cheapest": c.proposal_id if c else None, "fastest": f.proposal_id if f else None,
                "price_gap_mtoman": text(self.price_gap) if self.price_gap is not None else None,
                "duration_gap_weeks": self.duration_gap, "selected": self.selected,
                "decision_consistent": self.decision_consistent,
                "published_match": f"{self.published_match}/{self.published_total}"}


def evaluate(bp: Blueprint, registry: ProposalRegistry) -> Evaluation:
    weights = tuple(CriterionWeight(c.criterion_id, c.weight) for c in bp.criteria)
    out = Evaluation(registry.rfp_id, selected=registry.decision.selected if registry.decision else "")
    scores: list[ProposalScore] = []
    for p in registry.proposals:
        lines = tuple(ScoreLine(c.criterion_id, c.weight, p.scores[c.criterion_id],
                                q(p.scores[c.criterion_id] * c.weight))
                      for c in bp.criteria if c.criterion_id in p.scores)
        missing = tuple(s for s in bp.response_sections if s not in p.sections)
        try:
            weighted: Decimal | None = compute_weighted_score(dict(p.scores), weights).value
            error = ""
        except InvariantError as exc:
            weighted, error = None, str(exc)
        scores.append(ProposalScore(p.proposal_id, lines, weighted, p.published_weighted, p.price_mtoman,
                                    p.duration_weeks, missing, 0, error))
    order = sorted((s for s in scores if s.weighted is not None), key=lambda s: (-s.weighted, s.proposal_id))
    rank = {s.proposal_id: i for i, s in enumerate(order, start=1)}
    out.scores = [ProposalScore(s.proposal_id, s.lines, s.weighted, s.published, s.price, s.duration,
                                s.missing_sections, rank.get(s.proposal_id, 0), s.error) for s in scores]
    return out
