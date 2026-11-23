"""Key-issue prioritization model.

Every open issue becomes an ``IssueSignal`` (plain values copied from the
issue, its sub-issues, the projects and the gap report). The ``Weights`` say
how much each factor counts; they must be non-negative and sum to 1, so a
score is always between 0 and 100.

Factors (each normalized to [0, 1]):

==========  ==================================================================
priority    AR-SW-022 level: P1 = 1.0, P2 = 0.75, P3 = 0.5, P4 = 0.25
severity    critical 1.0, high 0.75, medium 0.5, low 0.25
urgency     urgency / 10
risk        risk / 10
dependents  dependents / dependents_cap
exposure    money at stake / exposure_cap_mtoman (decision amount or the
            remaining value of the project whose primary issue it is)
blocked     blocked sub-issues / sub-issues
gaps        open gaps on the issue / gaps_cap
spread      affected nodes / spread_cap
==========  ==================================================================
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from rag_core.shared_kernel.errors import InvariantError

FACTORS: tuple[str, ...] = ("priority", "severity", "urgency", "risk", "dependents", "exposure", "blocked", "gaps",
                            "spread")
PRIORITY_VALUE = {"P1": 1.0, "P2": 0.75, "P3": 0.5, "P4": 0.25}
SEVERITY_VALUE = {"critical": 1.0, "high": 0.75, "medium": 0.5, "low": 0.25}
CLOSED_STATUSES = frozenset({"resolved", "closed"})
WEIGHT_TOLERANCE = 1e-6


@dataclass(frozen=True)
class Weights:
    values: Mapping[str, float]

    def __post_init__(self) -> None:
        values = {k: float(v) for k, v in dict(self.values).items()}
        unknown = sorted(set(values) - set(FACTORS))
        if unknown:
            raise InvariantError(f"unknown priority factors: {', '.join(unknown)}")
        if any(v < 0 for v in values.values()):
            raise InvariantError("priority weights must be >= 0")
        full = {f: values.get(f, 0.0) for f in FACTORS}
        total = sum(full.values())
        if abs(total - 1.0) > WEIGHT_TOLERANCE:
            raise InvariantError(f"priority weights must sum to 1.0, got {total:.4f}")
        object.__setattr__(self, "values", full)

    def __getitem__(self, factor: str) -> float:
        return float(self.values[factor])

    def perturbed(self, factor: str, ratio: float) -> Weights:
        """Copy with one weight multiplied by ``ratio`` and all weights renormalized to sum 1."""
        raw = {f: self[f] * (ratio if f == factor else 1.0) for f in FACTORS}
        total = sum(raw.values())
        if total <= 0:
            raise InvariantError("perturbed weights sum to zero")
        return Weights({f: v / total for f, v in raw.items()})


@dataclass(frozen=True)
class Caps:
    dependents: int = 4
    exposure_mtoman: int = 1000
    gaps: int = 5
    spread: int = 6

    def __post_init__(self) -> None:
        if min(self.dependents, self.exposure_mtoman, self.gaps, self.spread) <= 0:
            raise InvariantError("priority caps must be > 0")


@dataclass(frozen=True)
class IssueSignal:
    issue_id: str
    title_en: str
    title_fa: str
    status: str
    priority: str = "P3"
    severity: str = "medium"
    urgency: int = 0
    risk: int = 0
    dependents: int = 0
    exposure_mtoman: int = 0
    subissues: int = 0
    blocked_subissues: int = 0
    gaps: int = 0
    affected_nodes: int = 0
    progress: int | None = None
    duplicate_of: str = ""

    def __post_init__(self) -> None:
        if not self.issue_id.strip():
            raise InvariantError("issue id is required")
        if self.blocked_subissues > self.subissues:
            raise InvariantError(f"{self.issue_id}: more blocked sub-issues than sub-issues")
        for name in ("urgency", "risk", "dependents", "exposure_mtoman", "gaps", "affected_nodes"):
            if getattr(self, name) < 0:
                raise InvariantError(f"{self.issue_id}: {name} cannot be negative")

    @property
    def is_open(self) -> bool:
        return self.status not in CLOSED_STATUSES and not self.duplicate_of


@dataclass(frozen=True)
class ScoredIssue:
    issue_id: str
    title_en: str
    title_fa: str
    score: float
    rank: int
    key: bool
    factors: dict[str, float] = field(default_factory=dict)        # normalized values
    contributions: dict[str, float] = field(default_factory=dict)  # weight x value x 100
    signal: IssueSignal | None = None

    def top_factors(self, n: int = 3) -> list[tuple[str, float]]:
        ranked = sorted(self.contributions.items(), key=lambda kv: (-kv[1], FACTORS.index(kv[0])))
        return [(k, v) for k, v in ranked if v > 0][:n]

    def to_dict(self) -> dict[str, object]:
        return {"issue_id": self.issue_id, "title_en": self.title_en, "title_fa": self.title_fa,
                "score": self.score, "rank": self.rank, "key": self.key, "factors": dict(self.factors),
                "contributions": dict(self.contributions),
                "top_factors": [k for k, _ in self.top_factors()]}
