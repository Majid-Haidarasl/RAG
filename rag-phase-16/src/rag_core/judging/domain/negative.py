"""Negative controls: deliberately broken copies of good outputs.

A judge that accepts these is not discriminating. Each mutation returns a new
``JudgeCase`` with ``gold="reject"`` and ``origin="negative:<kind>"``, or
``None`` when it does not apply (e.g. no number to change).

* ``wrong_number``        — every number outside labels and identifiers is changed (30 → 307);
* ``fabricated_citation`` — every bracket label points at a document that was never given;
* ``off_topic``           — the answer of another question (other documents) is returned;
* ``refuse_answerable``   — a refusal although the sources contain the answer;
* ``answer_unanswerable`` — a confident, labelled answer where a refusal was expected;
* ``drop_items``          — a summary that keeps only the first sub-issue;
* ``wrong_lead``          — a summary whose lead executors are rotated between sub-issues.
"""

from __future__ import annotations

import re
from enum import StrEnum

from rag_core.judging.domain.cases import JudgeCase
from rag_core.judging.domain.rubric import OutputKind
from rag_core.judging.domain.text import (
    BRACKET_RE,
    bracket_refs,
    contains_id,
    sentences,
    words,
)
from rag_core.shared_kernel.numerals import normalize_digits

FAKE_LABEL = "AR-ZZZ-999 §99"
# One capturing group only, so ``split`` alternates free text and protected spans.
_PROTECTED_RE = re.compile(
    r"(\[[^\[\]]{3,200}\]|\b(?:AR|PRJ|N|EX)-[A-Za-z0-9][A-Za-z0-9/\-]*|§\s*\d+)"
)
_NUMBER_RE = re.compile(r"(?<![A-Za-z0-9.\-/])(\d+)((?:\.\d+)?)(?![A-Za-z0-9])")

REFUSAL_TEXT = {
    "fa": "INSUFFICIENT_CONTEXT اسناد داده‌شده برای پاسخ به این پرسش کافی نیستند.",
    "en": "INSUFFICIENT_CONTEXT The provided documents are not enough to answer this question.",
}
FABRICATED_ANSWER = {
    "fa": "طبق سیاست شرکت، سقف این مورد ۱۲ روز در سال است و با تأیید مدیر واحد اجرا می‌شود [AR-HR-005 §4].",
    "en": "According to company policy, the limit is 12 days per year and the unit manager approves it [AR-HR-005 §4].",
}


class NegativeKind(StrEnum):
    WRONG_NUMBER = "wrong_number"
    FABRICATED_CITATION = "fabricated_citation"
    OFF_TOPIC = "off_topic"
    REFUSE_ANSWERABLE = "refuse_answerable"
    ANSWER_UNANSWERABLE = "answer_unanswerable"
    DROP_ITEMS = "drop_items"
    WRONG_LEAD = "wrong_lead"


ANSWER_ORDER = (
    NegativeKind.WRONG_NUMBER,
    NegativeKind.FABRICATED_CITATION,
    NegativeKind.OFF_TOPIC,
    NegativeKind.REFUSE_ANSWERABLE,
)
SUMMARY_ORDER = (NegativeKind.DROP_ITEMS, NegativeKind.WRONG_LEAD)


def _bump(match: re.Match[str]) -> str:
    return f"{int(match.group(1)) * 10 + 7}{match.group(2)}"


def wrong_number(case: JudgeCase) -> JudgeCase | None:
    text = normalize_digits(case.output)
    parts = _PROTECTED_RE.split(text)
    changed = 0
    out: list[str] = []
    for i, part in enumerate(parts):
        if i % 2 == 1 or not part:  # captured (protected) span
            out.append(part)
            continue
        new, n = _NUMBER_RE.subn(_bump, part)
        changed += n
        out.append(new)
    if not changed:
        return None
    return case.mutated(NegativeKind.WRONG_NUMBER.value, "".join(out))


def fabricated_citation(case: JudgeCase) -> JudgeCase | None:
    if not bracket_refs(case.output):
        return None
    return case.mutated(
        NegativeKind.FABRICATED_CITATION.value,
        BRACKET_RE.sub(f"[{FAKE_LABEL}]", case.output),
    )


def off_topic(case: JudgeCase, pool: list[JudgeCase]) -> JudgeCase | None:
    own = {r.document_id for r in bracket_refs(case.output)} | {
        b.document_id for b in case.sources
    }
    for other in pool:
        if (
            other.case_id == case.case_id
            or other.kind is not OutputKind.QA_ANSWER
            or other.refused
        ):
            continue
        if other.language != case.language or not other.output.strip():
            continue
        refs = {r.document_id for r in bracket_refs(other.output)}
        if refs and not refs & own:
            return case.mutated(NegativeKind.OFF_TOPIC.value, other.output)
    return None


def refuse_answerable(case: JudgeCase) -> JudgeCase | None:
    if case.kind is not OutputKind.QA_ANSWER:
        return None
    return case.mutated(
        NegativeKind.REFUSE_ANSWERABLE.value,
        REFUSAL_TEXT[case.language],
        status="insufficient_context",
    )


def answer_unanswerable(case: JudgeCase) -> JudgeCase | None:
    if case.kind is not OutputKind.QA_REFUSAL:
        return None
    return case.mutated(
        NegativeKind.ANSWER_UNANSWERABLE.value,
        FABRICATED_ANSWER[case.language],
        status="answered",
        escalation="",
    )


def drop_items(case: JudgeCase) -> JudgeCase | None:
    items = [i for i in case.expectation.items if contains_id(case.output, i)]
    if len(items) < 2:
        return None
    drop = items[1:]
    kept: list[str] = []
    for line in case.output.splitlines():
        parts = [s for s in sentences(line) if not any(contains_id(s, i) for i in drop)]
        if parts:
            kept.append(" ".join(parts))
    text = "\n".join(kept).strip()
    if not text or any(contains_id(text, i) for i in drop):
        return None
    return case.mutated(NegativeKind.DROP_ITEMS.value, text)


def _present_alternative(text: str, names: tuple[str, ...]) -> str | None:
    padded = f" {' '.join(words(text))} "
    for name in names:
        if name and f" {' '.join(words(name))} " in padded and name in text:
            return name
    return None


def wrong_lead(case: JudgeCase) -> JudgeCase | None:
    found: list[str] = []
    for _, names in case.expectation.item_leads:
        name = _present_alternative(case.output, names)
        if name and name not in found:
            found.append(name)
    if len(found) < 2:
        return None
    text = case.output
    for i, name in enumerate(found):
        text = text.replace(name, f"\x00{i}\x00")
    for i in range(len(found)):
        text = text.replace(f"\x00{i}\x00", found[(i + 1) % len(found)])
    return case.mutated(NegativeKind.WRONG_LEAD.value, text)


def negative_for(
    case: JudgeCase, index: int, pool: list[JudgeCase]
) -> JudgeCase | None:
    """One negative control per positive case; the preferred kind rotates with ``index``."""
    if case.kind is OutputKind.QA_REFUSAL:
        return answer_unanswerable(case)
    if case.kind is OutputKind.IKE_SUMMARY:
        order = SUMMARY_ORDER[index % 2 :] + SUMMARY_ORDER[: index % 2]
    else:
        start = index % len(ANSWER_ORDER)
        order = ANSWER_ORDER[start:] + ANSWER_ORDER[:start]
    for kind in order:
        made = _MAKERS[kind](case, pool)
        if made is not None:
            return made
    return None


_MAKERS = {
    NegativeKind.WRONG_NUMBER: lambda c, p: wrong_number(c),
    NegativeKind.FABRICATED_CITATION: lambda c, p: fabricated_citation(c),
    NegativeKind.OFF_TOPIC: off_topic,
    NegativeKind.REFUSE_ANSWERABLE: lambda c, p: refuse_answerable(c),
    NegativeKind.ANSWER_UNANSWERABLE: lambda c, p: answer_unanswerable(c),
    NegativeKind.DROP_ITEMS: lambda c, p: drop_items(c),
    NegativeKind.WRONG_LEAD: lambda c, p: wrong_lead(c),
}


def negative_controls(cases: list[JudgeCase]) -> list[JudgeCase]:
    """Negative controls for every positive (non-negative, gold != reject) case, in order."""
    pool = [c for c in cases if not c.is_negative and c.gold != "reject"]
    out: list[JudgeCase] = []
    for i, case in enumerate(pool):
        made = negative_for(case, i, pool)
        if made is not None:
            out.append(made)
    return out
