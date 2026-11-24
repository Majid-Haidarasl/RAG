"""Acceptance policy: total ≥ 18/20 *and* every criterion at or above its minimum.

* A total below ``accept_total`` rejects (the Phase 3 ``JudgeThreshold`` decides).
* A criterion below its minimum rejects even when the total is high enough,
  e.g. 3 + 5 + 4 + 3 + 3 = 18 fails because grounding 3 < 4.
* A missing criterion counts as 0 and is reported as ``missing:<key>``.
* ``hard_failures`` (e.g. a rule guard) reject with ``hard:<reason>``.
* A judge reply that cannot be parsed is an ``error`` — never an acceptance,
  and never a silent score of 0 (Phase 3 rule).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from rag_core.judging.domain.model import JudgeScore, Verdict
from rag_core.judging.domain.rubric import Rubric
from rag_core.shared_kernel.errors import InvariantError


class Decision(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"
    ERROR = "error"


@dataclass(frozen=True)
class PolicyOutcome:
    decision: Decision
    total: int
    out_of: int
    reasons: tuple[str, ...] = ()

    @property
    def accepted(self) -> bool:
        return self.decision is Decision.ACCEPT

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": self.decision.value,
            "total": self.total,
            "out_of": self.out_of,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class AcceptancePolicy:
    rubric: Rubric

    def decide(
        self,
        scores: Mapping[str, int],
        *,
        hard_failures: tuple[str, ...] | list[str] = (),
    ) -> PolicyOutcome:
        maximums = self.rubric.maximums
        unknown = sorted(set(scores) - set(maximums))
        if unknown:
            raise InvariantError(f"unknown criteria: {', '.join(unknown)}")
        for key, value in scores.items():
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or not 0 <= value <= maximums[key]
            ):
                raise InvariantError(f"{key}={value!r} is outside 0..{maximums[key]}")
        total = sum(scores.get(k, 0) for k in self.rubric.keys)
        reasons: list[str] = []
        if (
            self.rubric.threshold.verdict(JudgeScore(total, self.rubric.out_of))
            is Verdict.FAIL
        ):
            reasons.append(f"total {total}<{self.rubric.accept_total}")
        for c in self.rubric.criteria:
            if c.key not in scores:
                reasons.append(f"missing:{c.key}")
            elif scores[c.key] < c.min_points:
                reasons.append(f"{c.key} {scores[c.key]}<{c.min_points}")
        reasons.extend(f"hard:{h}" for h in hard_failures)
        decision = Decision.REJECT if reasons else Decision.ACCEPT
        return PolicyOutcome(decision, total, self.rubric.out_of, tuple(reasons))

    def error(self, reason: str) -> PolicyOutcome:
        return PolicyOutcome(
            Decision.ERROR, 0, self.rubric.out_of, (f"error:{reason}",)
        )
