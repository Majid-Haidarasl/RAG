"""Deterministic, explainable scoring and ranking of open issues."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from rag_core.prioritization.domain.model import (
    FACTORS,
    PRIORITY_VALUE,
    SEVERITY_VALUE,
    Caps,
    IssueSignal,
    ScoredIssue,
    Weights,
)
from rag_core.shared_kernel.errors import InvariantError


def _clamp(x: float) -> float:
    return 0.0 if x < 0 else (1.0 if x > 1 else x)


def factor_values(s: IssueSignal, caps: Caps) -> dict[str, float]:
    return {
        "priority": PRIORITY_VALUE.get(s.priority, 0.5),
        "severity": SEVERITY_VALUE.get(s.severity, 0.5),
        "urgency": _clamp(s.urgency / 10),
        "risk": _clamp(s.risk / 10),
        "dependents": _clamp(s.dependents / caps.dependents),
        "exposure": _clamp(s.exposure_mtoman / caps.exposure_mtoman),
        "blocked": _clamp(s.blocked_subissues / s.subissues) if s.subissues else 0.0,
        "gaps": _clamp(s.gaps / caps.gaps),
        "spread": _clamp(s.affected_nodes / caps.spread),
    }


def score(s: IssueSignal, weights: Weights, caps: Caps) -> tuple[float, dict[str, float], dict[str, float]]:
    values = factor_values(s, caps)
    contributions = {f: round(100 * weights[f] * values[f], 2) for f in FACTORS}
    total = round(100 * sum(weights[f] * values[f] for f in FACTORS), 2)
    return total, {f: round(v, 4) for f, v in values.items()}, contributions


@dataclass
class Ranking:
    ranked: list[ScoredIssue] = field(default_factory=list)
    excluded: list[tuple[str, str]] = field(default_factory=list)   # (issue id, reason)

    @property
    def key_ids(self) -> list[str]:
        return [r.issue_id for r in self.ranked if r.key]

    @property
    def order(self) -> list[str]:
        return [r.issue_id for r in self.ranked]

    def get(self, issue_id: str) -> ScoredIssue | None:
        return next((r for r in self.ranked if r.issue_id == issue_id), None)

    def to_dict(self) -> dict[str, object]:
        return {"ranked": [r.to_dict() for r in self.ranked], "excluded": [list(e) for e in self.excluded],
                "key": self.key_ids}


class PriorityScorer:
    def __init__(self, weights: Weights, caps: Caps | None = None, *, key_count: int = 3,
                 key_min_score: float = 25.0) -> None:
        if key_count < 1:
            raise InvariantError("key_count must be >= 1")
        if not 0 <= key_min_score <= 100:
            raise InvariantError("key_min_score must be in [0, 100]")
        self.weights = weights
        self.caps = caps or Caps()
        self.key_count = key_count
        self.key_min_score = key_min_score

    def rank(self, signals: Iterable[IssueSignal]) -> Ranking:
        scored: list[tuple[float, IssueSignal, dict[str, float], dict[str, float]]] = []
        excluded: list[tuple[str, str]] = []
        for s in signals:
            if s.duplicate_of:
                excluded.append((s.issue_id, f"duplicate_of:{s.duplicate_of}"))
                continue
            if not s.is_open:
                excluded.append((s.issue_id, s.status))
                continue
            total, values, contributions = score(s, self.weights, self.caps)
            scored.append((total, s, values, contributions))
        # Higher score first; ties: higher risk, then higher urgency, then issue id.
        scored.sort(key=lambda t: (-t[0], -t[1].risk, -t[1].urgency, t[1].issue_id))
        ranked: list[ScoredIssue] = []
        for i, (total, s, values, contributions) in enumerate(scored, start=1):
            key = i <= self.key_count and total >= self.key_min_score
            ranked.append(ScoredIssue(s.issue_id, s.title_en, s.title_fa, total, i, key, values, contributions, s))
        return Ranking(ranked, sorted(excluded))


def legacy_order(signals: Iterable[IssueSignal]) -> list[str]:
    """Phase 7 ``rank_issues`` formula (3*urgency + 2*risk + dependents) on the same open issues."""
    open_signals = [s for s in signals if s.is_open]
    return [s.issue_id for s in sorted(open_signals,
                                       key=lambda s: (-(3 * s.urgency + 2 * s.risk + s.dependents), s.issue_id))]


@dataclass(frozen=True)
class Sensitivity:
    perturbations: int
    top1_stable: int
    key_set_stable: int
    flips: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {"perturbations": self.perturbations, "top1_stable": self.top1_stable,
                "key_set_stable": self.key_set_stable, "flips": list(self.flips)}


def sensitivity(scorer: PriorityScorer, signals: list[IssueSignal], ratios: tuple[float, ...] = (0.8, 1.2)) -> Sensitivity:
    """Change each weight by each ratio (renormalized) and see if the top issue and the key set stay."""
    base = scorer.rank(signals)
    base_top = base.order[:1]
    base_keys = set(base.key_ids)
    n = top_ok = keys_ok = 0
    flips: list[str] = []
    for factor in FACTORS:
        if scorer.weights[factor] == 0:
            continue
        for ratio in ratios:
            other = PriorityScorer(scorer.weights.perturbed(factor, ratio), scorer.caps, key_count=scorer.key_count,
                                   key_min_score=scorer.key_min_score)
            r = other.rank(signals)
            n += 1
            if r.order[:1] == base_top:
                top_ok += 1
            if set(r.key_ids) == base_keys:
                keys_ok += 1
            else:
                flips.append(f"{factor}x{ratio}")
    return Sensitivity(n, top_ok, keys_ok, tuple(flips))
