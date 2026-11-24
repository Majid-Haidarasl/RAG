"""Deterministic pre-check in front of the strict LLM judge (Phase 15).

Phase 14 measured that the strict checklist prompt still let ``qwen3:8b``
accept 2 of 3 answers that dropped a reference fact (``drop_fact`` 1/3). The
pre-check counts what can be counted without a model:

* answers (``qa_answer``) — every reference fact group must be in the output
  (same word normalization as the rule judge: digits, yeh/kaf, ZWNJ,
  punctuation); an answer that refuses although facts are expected misses
  them all;
* summaries — every required id (``items``, item leads, gaps) must be named.

Refusal cases and cases without known facts or ids pass unchanged. A failed
pre-check rejects the output before the LLM is asked; a passed one leaves the
verdict to the LLM judge (``PrecheckedJudge``). The pre-check lives in the
application layer because it combines the judging context's case model and
text helpers with the tuning context's id helpers.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from rag_core.judging.domain.cases import JudgeCase
from rag_core.judging.domain.results import JudgeResult
from rag_core.judging.domain.rubric import OutputKind
from rag_core.judging.domain.text import groups_found
from rag_core.judging.domain.threshold import Decision, PolicyOutcome
from rag_core.tuning.domain.required_ids import missing_ids


@dataclass(frozen=True)
class PrecheckFinding:
    case_id: str
    applied: bool
    reasons: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return not self.reasons

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "applied": self.applied,
            "passed": self.passed,
            "reasons": list(self.reasons),
        }


def required_summary_ids(case: JudgeCase) -> tuple[str, ...]:
    exp = case.expectation
    return tuple(
        dict.fromkeys([*exp.items, *(i for i, _ in exp.item_leads), *exp.gaps])
    )


def fact_precheck(case: JudgeCase) -> PrecheckFinding:
    """What a case is missing that a reader can count: fact groups (answers) or ids (summaries)."""
    text = case.output or ""
    if case.kind is OutputKind.QA_REFUSAL:
        return PrecheckFinding(case.case_id, False)
    if case.kind is OutputKind.QA_ANSWER:
        groups = case.expectation.facts
        if not groups:
            return PrecheckFinding(case.case_id, False)
        hit, total = groups_found(text, groups)
        reasons = () if hit == total else (f"facts:{hit}/{total}",)
        return PrecheckFinding(case.case_id, True, reasons)
    required = required_summary_ids(case)
    if not required:
        return PrecheckFinding(case.case_id, False)
    missed = missing_ids(text, required)
    return PrecheckFinding(case.case_id, True, tuple(f"missing_id:{m}" for m in missed))


def precheck_summary(
    findings: list[PrecheckFinding], gold: dict[str, str], mutation: dict[str, str]
) -> dict[str, object]:
    """Counts for the summary: flagged cases, false flags (gold accept) and flags per mutation kind."""
    flagged = [f for f in findings if not f.passed]
    false_flags = [f.case_id for f in flagged if gold.get(f.case_id) == "accept"]
    per: dict[str, list[bool]] = {}
    for f in findings:
        kind = mutation.get(f.case_id)
        if kind:
            per.setdefault(kind, []).append(not f.passed)
    rejects = [f for f in findings if gold.get(f.case_id) == "reject"]
    return {
        "cases": len(findings),
        "applied": sum(1 for f in findings if f.applied),
        "flagged": len(flagged),
        "gold_rejects_flagged": sum(1 for f in rejects if not f.passed),
        "gold_rejects": len(rejects),
        "false_flags": false_flags,
        "by_mutation": {k: f"{sum(v)}/{len(v)}" for k, v in sorted(per.items())},
        "flagged_ids": [f.case_id for f in flagged],
    }


class PrecheckedJudge:
    """``fact_precheck`` in front of another judge (the strict LLM judge in Phase 15).

    A failed pre-check gives a ``reject`` result with ``precheck:`` reasons and no model call;
    otherwise the inner judge decides and its result is renamed to this judge.
    """

    def __init__(self, inner: Any, *, name: str = "precheck") -> None:
        self.inner = inner
        self.name = name
        self.policy = getattr(inner, "policy", None)
        self.prechecked = 0
        self.model_calls = 0

    def judge(self, case: JudgeCase) -> JudgeResult:
        finding = fact_precheck(case)
        if not finding.passed:
            self.prechecked += 1
            out_of = self.policy.rubric.out_of if self.policy is not None else 20
            outcome = PolicyOutcome(
                Decision.REJECT,
                0,
                out_of,
                tuple(f"precheck:{r}" for r in finding.reasons),
            )
            return JudgeResult.for_case(
                case,
                self.name,
                {},
                outcome,
                parse_mode="precheck",
                notes=tuple(f"precheck:{r}" for r in finding.reasons),
            )
        self.model_calls += 1
        return replace(self.inner.judge(case), judge=self.name)
