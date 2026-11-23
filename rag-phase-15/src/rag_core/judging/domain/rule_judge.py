"""Deterministic rule-based judge (offline, used by unit tests and the dry run).

It scores the same five criteria as the LLM judge from signals that can be
computed without a model:

* grounding    — numbers and identifiers in the output that are not in the
                 sources (shared-kernel ``FactValidator``; Phase 8
                 ``CitedFactValidator`` in production): −2 each;
* correctness  — share of reference key facts present (Phase 8 sample
                 questions); for summaries, each sub-issue named together
                 with its lead executor; for refusals, the right status;
* citation     — bracket labels must point at a given source (−2 per
                 fabricated label, −1 when most sentences carry none); for
                 summaries, the share of sub-issue ids mentioned;
* completeness — share of key facts (answers), the right escalation target
                 (out-of-scope refusals), the knowledge gaps (summaries);
* clarity      — output in the question language, no leftovers such as
                 ``<think>`` or code fences, not too long.

The rule judge is strict about what it can see and blind to meaning: two
correct numbers in swapped places look fine to it (see the calibration
case tagged ``rule_blind_spot``). That is what the LLM judge is for.
"""

from __future__ import annotations

from dataclasses import dataclass
import time

from rag_core.judging.domain.cases import NOT_FOUND_STATUSES, REFUSAL_STATUSES, JudgeCase, SourceBlock
from rag_core.judging.domain.parser import round_half_up
from rag_core.judging.domain.results import JudgeResult
from rag_core.judging.domain.rubric import OutputKind, Rubric
from rag_core.judging.domain.text import (
    CitedRef,
    bracket_refs,
    contains_id,
    groups_found,
    has_brackets,
    language_matches,
    sentences,
    strip_refs,
)
from rag_core.judging.domain.threshold import AcceptancePolicy
from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.fact_ports import FactValidator, FactVerdict
from rag_core.shared_kernel.numerals import normalize_digits

STANDARD_KEYS = ("grounding", "correctness", "citation", "completeness", "clarity")
ARTIFACTS = ("<think", "</think", "```", "/no_think")
REFUSAL_TOKEN = "INSUFFICIENT_CONTEXT"


@dataclass(frozen=True)
class RuleJudgeConfig:
    max_answer_chars: int = 1200
    max_answer_sentences: int = 6
    max_summary_chars: int = 3000
    min_refusal_chars: int = 20


def first_item(segment: str, items: tuple[str, ...]) -> str | None:
    """The sub-issue id that appears first in ``segment`` (``None`` if none does)."""
    upper = normalize_digits(segment).upper()
    found = [(upper.find(i.upper()), i) for i in items if i.upper() in upper]
    return min(found)[1] if found else None


def _looks_refused(text: str) -> bool:
    return REFUSAL_TOKEN in (text or "")[:200].upper().replace(" ", "_")


def citation_valid(ref: CitedRef, sources: tuple[SourceBlock, ...]) -> bool:
    for block in sources:
        if block.document_id.upper() != ref.document_id:
            continue
        if ref.order is not None and block.order != ref.order:
            continue
        if ref.language is not None and block.language is not None and block.language != ref.language:
            continue
        return True
    return False


class RuleBasedJudge:
    name = "rule"

    def __init__(self, rubric: Rubric, validator: FactValidator, config: RuleJudgeConfig | None = None) -> None:
        if tuple(sorted(rubric.keys)) != tuple(sorted(STANDARD_KEYS)):
            raise InvariantError("the rule judge needs the five standard criteria: " + ", ".join(STANDARD_KEYS))
        self.rubric = rubric
        self.validator = validator
        self.config = config or RuleJudgeConfig()
        self.policy = AcceptancePolicy(rubric)
        self.mx = rubric.maximums

    # -- public ------------------------------------------------------------------
    def judge(self, case: JudgeCase) -> JudgeResult:
        t0 = time.perf_counter()
        if case.kind is OutputKind.QA_ANSWER:
            scores, notes = self._answer(case)
        elif case.kind is OutputKind.QA_REFUSAL:
            scores, notes = self._refusal(case)
        else:
            scores, notes = self._summary(case)
        outcome = self.policy.decide(scores)
        return JudgeResult.for_case(case, self.name, scores, outcome, notes=tuple(notes), parse_mode="rules",
                                    seconds=time.perf_counter() - t0)

    # -- shared signals -------------------------------------------------------------
    def _claims(self, text: str, sources: tuple[SourceBlock, ...]) -> tuple[list[str], list[str]]:
        texts = [b.text for b in sources]
        docs = " ".join(b.document_id for b in sources if b.document_id)
        if docs:
            texts.append(docs)
        report = self.validator.validate(text, texts)
        unsupported = [r.claim.raw_text for r in report.results if r.verdict is FactVerdict.UNSUPPORTED]
        flagged = [r.claim.raw_text for r in report.results if r.verdict is FactVerdict.FLAGGED]
        return unsupported, flagged

    def _clarity(self, case: JudgeCase, text: str, *, answered: bool) -> tuple[int, list[str]]:
        top = self.mx["clarity"]
        match = language_matches(text, case.language)
        if match is False:
            return 0, ["wrong_language"]
        score = top
        notes: list[str] = []
        if match is None:
            score -= 1
            notes.append("language_unclear")
        summary = case.kind is OutputKind.IKE_SUMMARY
        limit = self.config.max_summary_chars if summary else self.config.max_answer_chars
        too_many = not summary and len(sentences(text)) > self.config.max_answer_sentences
        if len(text) > limit or too_many:
            score -= 1
            notes.append("too_long")
        lowered = text.lower()
        if any(a in lowered for a in ARTIFACTS) or (answered and REFUSAL_TOKEN in text.upper()):
            score -= 1
            notes.append("artifacts")
        if summary and sum(1 for line in text.splitlines() if line.count("|") >= 2) >= 2:
            score -= 1
            notes.append("table")
        return max(0, score), notes

    # -- QA answer expected -----------------------------------------------------------
    def _answer(self, case: JudgeCase) -> tuple[dict[str, int], list[str]]:
        text = case.output or ""
        mx = self.mx
        refused = case.refused or _looks_refused(text) or not strip_refs(text).strip()
        clarity, notes = self._clarity(case, text, answered=not refused)
        if refused:
            notes.append("refused_although_answerable")
            return {"grounding": mx["grounding"], "correctness": 0, "citation": 0, "completeness": 0,
                    "clarity": clarity}, notes
        if not case.sources:
            grounding = 0
            notes.append("no_sources")
        else:
            unsupported, flagged = self._claims(text, case.sources)
            grounding = max(0, mx["grounding"] - 2 * len(unsupported) - len(flagged))
            notes.extend(f"unsupported:{u}" for u in unsupported[:5])
            notes.extend(f"flagged:{f}" for f in flagged[:5])
        hit, total = groups_found(text, case.expectation.facts)
        if total:
            share = hit / total
            notes.append(f"facts:{hit}/{total}")
        else:
            share = grounding / mx["grounding"]
        correctness = round_half_up(mx["correctness"] * share)
        completeness = round_half_up(mx["completeness"] * share)
        refs = bracket_refs(text)
        if not refs:
            citation = 0
            notes.append("no_citation")
        else:
            invalid = [r for r in refs if not citation_valid(r, case.sources)]
            citation = mx["citation"] - 2 * len(invalid)
            notes.extend(f"invalid_citation:{r.label}" for r in invalid[:5])
            parts = sentences(text)
            uncited = [s for s in parts if not has_brackets(s)]
            if parts and 2 * len(uncited) > len(parts):
                citation -= 1
                notes.append("sparse_citations")
            citation = max(0, citation)
        return {"grounding": grounding, "correctness": correctness, "citation": citation,
                "completeness": completeness, "clarity": clarity}, notes

    # -- refusal / escalation expected ------------------------------------------------
    def _refusal(self, case: JudgeCase) -> tuple[dict[str, int], list[str]]:
        text = case.output or ""
        mx = self.mx
        exp = case.expectation
        token = _looks_refused(text)
        refused = case.refused or token
        refs = bracket_refs(text)
        clarity, notes = self._clarity(case, text, answered=False)
        if not refused:
            notes.append("answered_without_scope_evidence")
            return {"grounding": 0, "correctness": 0, "citation": 0 if refs else mx["citation"],
                    "completeness": 0, "clarity": clarity}, notes
        status = case.status if case.status in REFUSAL_STATUSES else "insufficient_context"
        if exp.status == "out_of_scope":
            status_ok = status == "out_of_scope"
        elif exp.status == "not_found":
            status_ok = status in NOT_FOUND_STATUSES
        else:
            status_ok = True
        if not status_ok:
            notes.append(f"status:{status}!={exp.status}")
        correctness = mx["correctness"] if status_ok else round_half_up(mx["correctness"] * 0.4)
        grounding = mx["grounding"] if not refs else max(0, mx["grounding"] - 2)
        citation = mx["citation"] if not refs else max(0, mx["citation"] - 2)
        if refs:
            notes.append("refusal_with_citations")
        top = mx["completeness"]
        if exp.status == "out_of_scope":
            if exp.escalation:
                completeness = top if case.escalation == exp.escalation else (min(1, top) if case.escalation else 0)
            else:
                completeness = top if case.escalation else min(1, top)
            if case.escalation != exp.escalation:
                notes.append(f"escalation:{case.escalation or '-'}")
        else:
            long_enough = len(strip_refs(text).strip()) >= self.config.min_refusal_chars
            completeness = top if long_enough else min(1, top)
        return {"grounding": grounding, "correctness": correctness, "citation": citation,
                "completeness": completeness, "clarity": clarity}, notes

    # -- IKE summary --------------------------------------------------------------------
    def _summary(self, case: JudgeCase) -> tuple[dict[str, int], list[str]]:
        text = case.output or ""
        mx = self.mx
        exp = case.expectation
        if not text.strip():
            return {k: 0 for k in STANDARD_KEYS}, ["empty"]
        clarity, notes = self._clarity(case, text, answered=True)
        unsupported, flagged = self._claims(text, case.sources)
        grounding = max(0, mx["grounding"] - 2 * (len(unsupported) + len(flagged)))
        notes.extend(f"unsupported:{u}" for u in unsupported[:5])
        if exp.item_leads:
            parts = sentences(text)
            all_items = tuple(dict.fromkeys([*exp.items, *(i for i, _ in exp.item_leads)]))
            ok = 0
            for item, names in exp.item_leads:
                # Prefer segments about this sub-issue (its id comes first); "WIN depends on HW" is about WIN.
                segs = [s for s in parts if first_item(s, all_items) == item]
                segs = segs or [s for s in parts if contains_id(s, item)]
                if any(groups_found(s, (names,))[0] for s in segs):
                    ok += 1
                else:
                    notes.append(f"lead_missing:{item}")
            correctness = round_half_up(mx["correctness"] * ok / len(exp.item_leads))
        else:
            correctness = mx["correctness"]
        if exp.items:
            mentioned = sum(1 for i in exp.items if contains_id(text, i))
            citation = round_half_up(mx["citation"] * mentioned / len(exp.items))
            notes.append(f"items:{mentioned}/{len(exp.items)}")
        else:
            citation = mx["citation"]
        gaps = sorted(set(exp.gaps))
        if gaps:
            found = sum(1 for g in gaps if contains_id(text, g))
            completeness = round_half_up(mx["completeness"] * found / len(gaps))
            notes.append(f"gaps:{found}/{len(gaps)}")
        else:
            completeness = mx["completeness"]
        return {"grounding": grounding, "correctness": correctness, "citation": citation,
                "completeness": completeness, "clarity": clarity}, notes
