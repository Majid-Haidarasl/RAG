"""Anti-corruption layer to the judging context (Phase 10).

* ``derive_calibration`` turns the gold set into more calibration cases: per
  answered pair one reference answer (gold accept) in one language and one
  broken answer (gold reject) in the other language. The broken answer
  rotates over the mutation kinds below, so every kind is covered.
* ``ChecklistJudgePrompt`` is a ``JudgePromptSet`` with one more variable,
  ``${checklist}``: the reference facts (answers), the refusal behaviour
  (refusals) or the required ids (summaries), one numbered line each.
* ``load_strict_prompts`` reads ``config/prompts/judge_strict``.

Mutation kinds:

* ``drop_fact``          — the item's partial answer (at most half of the facts);
* ``wrong_number``       — the last number of the reference changed to one that
                           is not in the sources;
* ``wrong_language``     — the reference answer of the other language;
* ``fake_label``         — every bracket label points at a document that is not
                           a source;
* ``refuse_answerable``  — a refusal although the sources answer the question.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import yaml

from rag_core.judging.domain.cases import Expectation, JudgeCase, SourceBlock
from rag_core.judging.domain.prompts import JudgePromptSet
from rag_core.judging.domain.rubric import OutputKind, Rubric
from rag_core.judging.infrastructure.prompt_yaml import KINDS, prompt_from_dict
from rag_core.qa.domain.fact_check import source_numbers
from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.numerals import normalize_digits
from rag_core.tuning.domain.gold import GoldItem, pairs

MUTATIONS = (
    "drop_fact",
    "wrong_number",
    "wrong_language",
    "fake_label",
    "refuse_answerable",
)
DECOY_DOCS = ("AR-HR-011", "AR-HR-004")
REFUSALS = {
    "fa": "INSUFFICIENT_CONTEXT در منابع این گره پاسخی برای این پرسش پیدا نشد.",
    "en": "INSUFFICIENT_CONTEXT The sources in this scope do not answer this question.",
}
PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_NUMBER_RE = re.compile(r"\d{1,3}(?:[,٬]\d{3})+|\d+(?:[.٫]\d+)?")
_BRACKET_RE = re.compile(r"\[[^\[\]]*\]")
_ID_RE = re.compile(r"\b(?:AR|PRJ|N|EX)-[A-Za-z0-9۰-۹][A-Za-z0-9۰-۹/\-]*")
_LABEL_DOC_RE = re.compile(r"AR-[A-Z]{2,5}-\d{2,4}")


def source_blocks(item: GoldItem) -> tuple[SourceBlock, ...]:
    return tuple(
        SourceBlock(label, e.quote, e.document_id, i, e.language)
        for i, (label, e) in enumerate(zip(item.labels, item.evidence), 1)
    )


def answer_case(
    item: GoldItem,
    output: str,
    *,
    case_id: str,
    gold: str,
    origin: str,
    status: str = "answered",
    tags: tuple[str, ...] = (),
) -> JudgeCase:
    return JudgeCase(
        case_id=case_id,
        kind=OutputKind.QA_ANSWER,
        language=item.language,
        task=item.question,
        output=output,
        sources=source_blocks(item),
        expectation=Expectation(status="answered", facts=item.expected_facts),
        status=status,
        node=item.node,
        origin=origin,
        gold=gold,
        tags=tags,
    )


def _protected(text: str) -> list[tuple[int, int]]:
    return [
        (m.start(), m.end()) for r in (_BRACKET_RE, _ID_RE) for m in r.finditer(text)
    ]


def _to_text(value: Decimal, like: str) -> str:
    persian = any(ch in PERSIAN_DIGITS for ch in like)
    if any(sep in like for sep in ",٬"):
        body = f"{int(value):,}".replace(",", "٬" if persian else ",")
    else:
        body = format(value.normalize(), "f")
        if "." in body and body.endswith(".0"):
            body = body[:-2]
        if persian:
            body = body.replace(".", "٫")
    if persian:
        body = "".join(PERSIAN_DIGITS[int(ch)] if ch.isdigit() else ch for ch in body)
    return body


def wrong_number(text: str, sources: Sequence[str]) -> str | None:
    """``text`` with its last number (outside labels and ids) replaced by a value not in ``sources``."""
    blocked = _protected(text)
    spans = [
        m
        for m in _NUMBER_RE.finditer(text)
        if not any(a <= m.start() < b for a, b in blocked)
    ]
    if not spans:
        return None
    m = spans[-1]
    raw = (
        normalize_digits(m.group(0)).replace(",", "").replace("٬", "").replace("٫", ".")
    )
    value = Decimal(raw)
    known = source_numbers(list(sources))
    for offset in (7, 11, 13, 17, 19):
        new = value + offset
        if new.normalize() not in known:
            return text[: m.start()] + _to_text(new, m.group(0)) + text[m.end() :]
    return None


def fake_label(text: str, documents: Iterable[str]) -> str | None:
    docs = set(documents)
    decoy = next((d for d in DECOY_DOCS if d not in docs), None)
    if decoy is None or not _BRACKET_RE.search(text):
        return None
    return _BRACKET_RE.sub(lambda m: _LABEL_DOC_RE.sub(decoy, m.group(0)), text)


def mutate(item: GoldItem, kind: str, other: GoldItem | None) -> tuple[str, str] | None:
    """(output, system status) of one mutation, or ``None`` when it does not apply to the item."""
    ref = item.reference_answer
    if kind == "drop_fact":
        return (
            (item.partial_answer, "answered") if item.partial_answer.strip() else None
        )
    if kind == "wrong_number":
        out = wrong_number(ref, [e.quote for e in item.evidence])
        return (out, "answered") if out else None
    if kind == "wrong_language":
        if (
            other is None
            or other.language == item.language
            or not other.reference_answer.strip()
        ):
            return None
        return other.reference_answer, "answered"
    if kind == "fake_label":
        out = fake_label(ref, [e.document_id for e in item.evidence])
        return (out, "answered") if out else None
    if kind == "refuse_answerable":
        return REFUSALS[item.language], "insufficient_context"
    raise InvariantError(f"unknown mutation {kind}")


@dataclass(frozen=True)
class DerivedCase:
    case: JudgeCase
    mutation: str  # "" for the reference answer


def derive_calibration(items: Iterable[GoldItem]) -> list[DerivedCase]:
    out: list[DerivedCase] = []
    answered = [
        (p, by)
        for p, by in pairs(items).items()
        if set(by) == {"fa", "en"} and by["fa"].answered
    ]
    for i, (pair_id, by) in enumerate(answered):
        good_lang = "fa" if i % 2 == 0 else "en"
        bad_lang = "en" if good_lang == "fa" else "fa"
        good, bad = by[good_lang], by[bad_lang]
        out.append(
            DerivedCase(
                answer_case(
                    good,
                    good.reference_answer,
                    case_id=f"CAL14-{pair_id}-{good_lang}-ok",
                    gold="accept",
                    origin="calibration-derived",
                    tags=("derived",),
                ),
                "",
            )
        )
        rotation = MUTATIONS[i % len(MUTATIONS) :] + MUTATIONS[: i % len(MUTATIONS)]
        for kind in rotation:
            made = mutate(bad, kind, good)
            if made is None:
                continue
            output, status = made
            out.append(
                DerivedCase(
                    answer_case(
                        bad,
                        output,
                        case_id=f"CAL14-{pair_id}-{bad_lang}-{kind}",
                        gold="reject",
                        origin=f"negative:{kind}",
                        status=status,
                        tags=("derived", kind),
                    ),
                    kind,
                )
            )
            break
    return out


def expanded_calibration(
    base: Sequence[JudgeCase], items: Iterable[GoldItem]
) -> list[JudgeCase]:
    cases = [*base, *(d.case for d in derive_calibration(items))]
    ids = [c.case_id for c in cases]
    if len(ids) != len(set(ids)):
        raise InvariantError("duplicate case ids in the expanded calibration set")
    return cases


# ---- checklist prompt -------------------------------------------------------------------
def checklist_lines(case: JudgeCase) -> list[str]:
    exp = case.expectation
    lines: list[str] = []
    if case.kind is OutputKind.QA_ANSWER:
        for group in exp.facts:
            alts = " | ".join(group)
            lines.append(f"The output states: {alts}")
        if not exp.facts:
            lines.append("Every statement of the output is supported by the SOURCES")
        lines.append(
            "Every number, name and document id in the output appears in the SOURCES"
        )
        lines.append(
            "Every factual sentence ends with a bracket label of a SOURCES block"
        )
    elif case.kind is OutputKind.QA_REFUSAL:
        lines.append(
            "The output declines to answer and states no facts from outside its scope"
        )
        if exp.status == "out_of_scope" and exp.escalation:
            lines.append(f"The output suggests escalation to {exp.escalation}")
        else:
            lines.append("The output says briefly what is missing")
    else:
        required = list(
            dict.fromkeys([*exp.items, *(i for i, _ in exp.item_leads), *exp.gaps])
        )
        lines.extend(f"The summary writes the id {r}" for r in required)
        for item, names in exp.item_leads:
            lines.append(f"{item} is named with its lead: {' | '.join(names)}")
        lines.append("Every identifier and number in the summary appears in the FACTS")
    lines.append(
        f"The output is written in {'Persian' if case.language == 'fa' else 'English'}"
    )
    return [f"{i}. {line}" for i, line in enumerate(lines, 1)]


@dataclass(frozen=True)
class ChecklistJudgePrompt(JudgePromptSet):
    def __post_init__(self) -> None:
        super().__post_init__()
        if "${checklist}" not in self.system + self.user:
            raise InvariantError(
                f"{self.prompt_id}: a strict prompt must use ${{checklist}}"
            )

    def variables(
        self, case: JudgeCase, rubric: Rubric, sources_char_budget: int
    ) -> dict[str, str]:
        values = super().variables(case, rubric, sources_char_budget)
        values["checklist"] = "\n".join(checklist_lines(case))
        return values


def strict_prompt_from_dict(data: dict) -> ChecklistJudgePrompt:
    base = prompt_from_dict(data)
    return ChecklistJudgePrompt(
        base.prompt_id,
        base.version,
        base.kinds,
        base.system,
        base.user,
        base.retry_note,
        base.scope_notes,
        base.language_names,
    )


def load_strict_prompts(directory: Path) -> dict[str, ChecklistJudgePrompt]:
    by_kind: dict[str, ChecklistJudgePrompt] = {}
    for path in sorted(Path(directory).glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict) or data.get("type") != "prompt":
            continue
        prompt = strict_prompt_from_dict(data)
        for kind in prompt.kinds:
            if kind in by_kind:
                raise InvariantError(f"output kind {kind} has two strict prompts")
            by_kind[kind] = prompt
    missing = [k for k in KINDS if k not in by_kind]
    if missing:
        raise InvariantError(f"no strict judge prompt for: {', '.join(missing)}")
    return by_kind
