"""Variants under comparison and the rule that picks one.

A *candidate* is one variant with its measured metrics. ``pick`` ranks the
candidates by the primary metric (then the tie-breakers, then the variant
order given) and keeps the baseline unless the best one beats it by at least
``min_gain`` on the primary metric: a change has to earn its place.

The chosen variant per kind is written by hand in ``config/eval.yaml`` with a
reason; the script prints its own measured recommendation next to it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from rag_core.shared_kernel.errors import InvariantError

KINDS = (
    "retrieval",
    "qa_prompt",
    "judge_prompt",
    "ai_ids",
    "generation_model",
    "embedding_model",
)


@dataclass(frozen=True)
class Candidate:
    variant_id: str
    metrics: Mapping[str, float | None] = field(default_factory=dict)

    def value(self, name: str) -> float | None:
        v = self.metrics.get(name)
        return None if v is None else float(v)


@dataclass(frozen=True)
class SelectionRule:
    primary: str
    higher_is_better: bool = True
    tie_breakers: tuple[tuple[str, bool], ...] = ()  # (metric, higher_is_better)
    min_gain: float = 0.0

    def __post_init__(self) -> None:
        if not self.primary.strip():
            raise InvariantError("a selection rule needs a primary metric")
        if self.min_gain < 0:
            raise InvariantError("min_gain must be >= 0")


@dataclass(frozen=True)
class Pick:
    winner: str
    reason: str
    order: tuple[str, ...]
    measured: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "winner": self.winner,
            "reason": self.reason,
            "order": list(self.order),
            "measured": self.measured,
        }


def _key(c: Candidate, rule: SelectionRule, position: int) -> tuple:
    def part(name: str, higher: bool) -> tuple[int, float]:
        v = c.value(name)
        if v is None:
            return (1, 0.0)  # unmeasured sorts last
        return (0, -v if higher else v)

    parts = [part(rule.primary, rule.higher_is_better)]
    parts += [part(name, higher) for name, higher in rule.tie_breakers]
    return (*parts, position)


def pick(candidates: Sequence[Candidate], rule: SelectionRule, baseline: str) -> Pick:
    if not candidates:
        raise InvariantError("nothing to pick from")
    ids = [c.variant_id for c in candidates]
    if baseline not in ids:
        raise InvariantError(f"baseline {baseline} is not a candidate")
    ranked = sorted(enumerate(candidates), key=lambda t: _key(t[1], rule, t[0]))
    order = tuple(c.variant_id for _, c in ranked)
    best = ranked[0][1]
    base = candidates[ids.index(baseline)]
    bv, basev = best.value(rule.primary), base.value(rule.primary)
    if bv is None:
        return Pick(
            baseline,
            f"{rule.primary} not measured; keep {baseline}",
            order,
            measured=False,
        )
    if best.variant_id == baseline:
        return Pick(baseline, f"{rule.primary}={_fmt(bv)} is the best value", order)
    gain = (bv - basev) if basev is not None else None
    if gain is not None and not rule.higher_is_better:
        gain = -gain
    if gain is not None and gain < rule.min_gain:
        return Pick(
            baseline,
            f"{best.variant_id} {rule.primary}={_fmt(bv)} vs {baseline} {_fmt(basev)}: "
            f"gain below {rule.min_gain}; keep {baseline}",
            order,
        )
    return Pick(
        best.variant_id, f"{rule.primary}={_fmt(bv)} vs {baseline} {_fmt(basev)}", order
    )


def _fmt(v: float | None) -> str:
    return "-" if v is None else f"{v:g}"


@dataclass(frozen=True)
class Selection:
    kind: str
    variant: str
    reason: str


def selection_problems(
    selected: Mapping[str, Selection], known: Mapping[str, Sequence[str]]
) -> list[str]:
    """Every kind is chosen once, the chosen variant exists and has a written reason."""
    out: list[str] = []
    for kind in KINDS:
        if kind not in selected:
            out.append(f"missing:{kind}")
    for kind, sel in selected.items():
        if kind not in KINDS:
            out.append(f"unknown_kind:{kind}")
            continue
        if kind in known and sel.variant not in known[kind]:
            out.append(f"unknown_variant:{kind}={sel.variant}")
        if len(sel.reason.split()) < 5:
            out.append(f"missing_reason:{kind}")
    return out
