"""Judge score, threshold, rubric and evaluation aggregate."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import json
from typing import Any, Protocol

from rag_core.shared_kernel.errors import DomainError, InvariantError
from rag_core.shared_kernel.events import DomainEvent


class JudgeParseError(DomainError):
    """The judge returned malformed JSON."""


class Verdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"


@dataclass(frozen=True)
class JudgeScore:
    value: int
    out_of: int = 20

    def __post_init__(self) -> None:
        if self.out_of <= 0:
            raise InvariantError("out_of must be positive")
        if self.value < 0 or self.value > self.out_of:
            raise InvariantError(f"score {self.value} is outside 0..{self.out_of}")


@dataclass(frozen=True)
class JudgeThreshold:
    minimum: int
    out_of: int = 20

    def __post_init__(self) -> None:
        if self.minimum < 0 or self.minimum > self.out_of:
            raise InvariantError("invalid threshold")

    def verdict(self, score: JudgeScore) -> Verdict:
        if score.out_of != self.out_of:
            raise InvariantError("score and threshold use different scales")
        return Verdict.PASS if score.value >= self.minimum else Verdict.FAIL


@dataclass(frozen=True)
class JudgeRubric:
    name: str
    threshold: JudgeThreshold = field(default_factory=lambda: JudgeThreshold(18, 20))

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise InvariantError("rubric name is required")


@dataclass
class JudgeEvaluation:
    rubric: JudgeRubric
    raw_output: str
    score: JudgeScore
    verdict: Verdict
    events: list[DomainEvent] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw_output: str, rubric: JudgeRubric | None = None) -> JudgeEvaluation:
        rubric = rubric or JudgeRubric("default")
        score = parse_judge_output(raw_output)
        verdict = rubric.threshold.verdict(score)
        evaluation = cls(rubric=rubric, raw_output=raw_output, score=score, verdict=verdict)
        if verdict is Verdict.FAIL:
            evaluation.events.append(
                DomainEvent("JudgeScoreBelowThreshold", {"score": score.value, "minimum": rubric.threshold.minimum})
            )
        return evaluation


def parse_judge_output(raw: str) -> JudgeScore:
    text = raw.strip()
    if not text:
        raise JudgeParseError("empty judge output")
    try:
        payload: Any = json.loads(text)
    except json.JSONDecodeError as exc:
        raise JudgeParseError(f"malformed JSON: {exc}") from exc
    if not isinstance(payload, dict) or "score" not in payload:
        raise JudgeParseError("JSON must be an object with a score field")
    try:
        value = int(payload["score"])
        out_of = int(payload.get("out_of", 20))
    except (TypeError, ValueError) as exc:
        raise JudgeParseError("score must be an integer") from exc
    return JudgeScore(value, out_of)


class JudgePort(Protocol):
    """Used by RAG Core, Knowledge Transfer and RFP. Fakes implement this in tests."""

    def evaluate(self, subject: str, source: str, rubric: JudgeRubric) -> str:
        """Return raw JSON text that ``parse_judge_output`` can read."""
        ...
