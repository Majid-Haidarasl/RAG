"""One judgement of one case by one judge."""

from __future__ import annotations

from dataclasses import dataclass, field

from rag_core.judging.domain.cases import JudgeCase
from rag_core.judging.domain.threshold import Decision, PolicyOutcome


@dataclass(frozen=True)
class JudgeResult:
    case_id: str
    judge: str
    kind: str
    origin: str
    gold: str
    scores: dict[str, int]
    outcome: PolicyOutcome
    notes: tuple[str, ...] = ()
    parse_mode: str = ""
    warnings: tuple[str, ...] = ()
    raw: str = ""
    seconds: float = 0.0
    attempts: int = 1
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tags: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def for_case(
        cls,
        case: JudgeCase,
        judge: str,
        scores: dict[str, int],
        outcome: PolicyOutcome,
        **extra: object,
    ) -> JudgeResult:
        return cls(
            case.case_id,
            judge,
            case.kind.value,
            case.origin,
            case.gold,
            dict(scores),
            outcome,
            tags=case.tags,
            **extra,
        )  # type: ignore[arg-type]

    @property
    def accepted(self) -> bool:
        return self.outcome.accepted

    @property
    def decision(self) -> Decision:
        return self.outcome.decision

    @property
    def total(self) -> int:
        return self.outcome.total

    @property
    def is_negative(self) -> bool:
        return self.origin.startswith("negative:")

    @property
    def agrees_with_gold(self) -> bool | None:
        if not self.gold:
            return None
        return self.accepted == (self.gold == "accept")

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "judge": self.judge,
            "kind": self.kind,
            "origin": self.origin,
            "gold": self.gold,
            "scores": dict(self.scores),
            "total": self.total,
            "out_of": self.outcome.out_of,
            "decision": self.decision.value,
            "reasons": list(self.outcome.reasons),
            "notes": list(self.notes),
            "parse_mode": self.parse_mode,
            "warnings": list(self.warnings),
            "raw": self.raw,
            "seconds": round(self.seconds, 3),
            "attempts": self.attempts,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "tags": list(self.tags),
        }
