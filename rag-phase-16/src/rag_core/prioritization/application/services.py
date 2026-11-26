"""Prioritization use case: rank open issues, explain, test sensitivity, pick the next action."""

from __future__ import annotations

from dataclasses import dataclass, field

from rag_core.prioritization.domain.model import IssueSignal
from rag_core.prioritization.domain.scoring import (
    PriorityScorer,
    Ranking,
    Sensitivity,
    legacy_order,
    sensitivity,
)
from rag_core.prioritization.domain.unblocking import NextAction, SubTask, next_actions

FACTOR_LABELS_EN = {
    "priority": "priority",
    "severity": "severity",
    "urgency": "urgency",
    "risk": "risk",
    "dependents": "dependents",
    "exposure": "money at stake",
    "blocked": "blocked sub-issues",
    "gaps": "open gaps",
    "spread": "affected nodes",
}
FACTOR_LABELS_FA = {
    "priority": "اولویت",
    "severity": "شدت",
    "urgency": "فوریت",
    "risk": "ریسک",
    "dependents": "وابسته‌ها",
    "exposure": "مبلغ در خطر",
    "blocked": "زیرمسئله‌های مسدود",
    "gaps": "شکاف‌های باز",
    "spread": "گره‌های درگیر",
}


@dataclass
class PrioritizationResult:
    ranking: Ranking
    legacy: list[str]
    sensitivity: Sensitivity
    next_actions: dict[str, list[NextAction]] = field(default_factory=dict)

    @property
    def same_top1(self) -> bool:
        return bool(self.ranking.order) and self.ranking.order[:1] == self.legacy[:1]

    def top_overlap(self, n: int) -> int:
        return len(set(self.ranking.order[:n]) & set(self.legacy[:n]))

    def to_dict(self) -> dict[str, object]:
        return {
            **self.ranking.to_dict(),
            "legacy_order": list(self.legacy),
            "same_top1": self.same_top1,
            "sensitivity": self.sensitivity.to_dict(),
            "next_actions": {
                k: [a.to_dict() for a in v] for k, v in self.next_actions.items()
            },
        }


class PrioritizationService:
    def __init__(
        self, scorer: PriorityScorer, ratios: tuple[float, ...] = (0.8, 1.2)
    ) -> None:
        self.scorer = scorer
        self.ratios = tuple(ratios)

    def run(
        self, signals: list[IssueSignal], tasks: dict[str, list[SubTask]] | None = None
    ) -> PrioritizationResult:
        ranking = self.scorer.rank(signals)
        actions: dict[str, list[NextAction]] = {}
        for issue_id in ranking.key_ids:
            found = next_actions((tasks or {}).get(issue_id, []))
            if found:
                actions[issue_id] = found
        return PrioritizationResult(
            ranking,
            legacy_order(signals),
            sensitivity(self.scorer, signals, self.ratios),
            actions,
        )


def explain(scored, language: str = "en", n: int = 3) -> str:
    """``risk 12.0, urgency 12.0, priority 11.25`` (points out of 100) for one scored issue."""
    labels = FACTOR_LABELS_FA if language == "fa" else FACTOR_LABELS_EN
    return ", ".join(f"{labels[k]} {v:g}" for k, v in scored.top_factors(n))
