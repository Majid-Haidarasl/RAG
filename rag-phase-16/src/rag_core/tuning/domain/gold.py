"""Gold question/answer items (``eval/datasets/armanrayan-qa.jsonl``) and their validation.

A gold item is one question asked from one node in one language. The two
languages of the same question form a *pair* (``P01`` … ``P16``). For an
answered item the expected facts must be visible in its evidence quotes and
in its reference answer; ``§n`` in a reference label means the n-th evidence
quote of the item (not a section of the corpus document). A *partial answer*
(for items with two or more fact groups) states at most half of the facts:
it is the "missing facts" negative control of the derived calibration set.

Text matching is injected (``FactsFound``, ``LanguageCheck``) so this module
stays free of other contexts.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from rag_core.shared_kernel.errors import InvariantError

GOLD_STATUSES = ("answered", "out_of_scope", "not_found")
DETAILS = ("short", "list", "refusal")
LANGUAGES = ("fa", "en")
REFUSAL_TOKEN = "INSUFFICIENT_CONTEXT"
LABEL_RE = re.compile(r"\[([^\[\]]{3,200})\]")
LABEL_PART_RE = re.compile(r"^\s*(AR-[A-Z]{2,5}-\d{2,4})\s*§\s*(\d+)\s*$")

FactGroups = tuple[tuple[str, ...], ...]
FactsFound = Callable[[str, FactGroups], tuple[int, int]]
LanguageCheck = Callable[[str, str], "bool | None"]


@dataclass(frozen=True)
class Evidence:
    document_id: str
    language: str
    quote: str

    def __post_init__(self) -> None:
        if not self.document_id.strip() or not self.quote.strip():
            raise InvariantError("evidence needs a document id and a quote")
        if self.language not in LANGUAGES:
            raise InvariantError(
                f"evidence language must be fa or en, not {self.language!r}"
            )


@dataclass(frozen=True)
class GoldItem:
    id: str
    pair: str
    language: str
    node: str
    question: str
    expected_status: str
    expected_docs: tuple[str, ...] = ()
    expected_outside_docs: tuple[str, ...] = ()
    expected_escalation: str = ""
    expected_facts: FactGroups = ()
    evidence: tuple[Evidence, ...] = ()
    reference_answer: str = ""
    partial_answer: str = ""
    detail: str = "short"
    origin: str = ""

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.pair.strip():
            raise InvariantError("a gold item needs an id and a pair")
        if self.language not in LANGUAGES:
            raise InvariantError(f"{self.id}: language must be fa or en")
        if self.expected_status not in GOLD_STATUSES:
            raise InvariantError(
                f"{self.id}: unknown expected_status {self.expected_status!r}"
            )
        if self.detail not in DETAILS:
            raise InvariantError(f"{self.id}: unknown detail {self.detail!r}")
        if not self.question.strip() or not self.node.strip():
            raise InvariantError(f"{self.id}: question and node are required")

    @property
    def answered(self) -> bool:
        return self.expected_status == "answered"

    @property
    def labels(self) -> tuple[str, ...]:
        """Source labels of the evidence quotes: ``AR-SW-022 §1``, ``AR-SW-022 §2``, …"""
        return tuple(f"{e.document_id} §{i}" for i, e in enumerate(self.evidence, 1))

    @property
    def phase8_id(self) -> str:
        return self.origin.split(":", 1)[1] if self.origin.startswith("phase8:") else ""

    @property
    def quote_text(self) -> str:
        return "\n".join(e.quote for e in self.evidence)


@dataclass(frozen=True)
class GoldProblem:
    code: str
    ref: str
    detail: str = ""

    def __str__(self) -> str:
        return f"{self.code}:{self.ref}" + (f" ({self.detail})" if self.detail else "")


def cited_labels(text: str) -> list[tuple[str, int] | None]:
    """Every label inside square brackets as (document id, n); ``None`` for a part that is not ``DOC §n``."""
    out: list[tuple[str, int] | None] = []
    for m in LABEL_RE.finditer(text or ""):
        for part in re.split(r"[;؛]", m.group(1)):
            lm = LABEL_PART_RE.match(part)
            out.append((lm.group(1), int(lm.group(2))) if lm else None)
    return out


def pairs(items: Iterable[GoldItem]) -> dict[str, dict[str, GoldItem]]:
    out: dict[str, dict[str, GoldItem]] = {}
    for item in items:
        out.setdefault(item.pair, {})[item.language] = item
    return dict(sorted(out.items()))


def _pair_problems(pair_id: str, by_lang: dict[str, GoldItem]) -> list[GoldProblem]:
    if set(by_lang) != set(LANGUAGES):
        return [GoldProblem("pair_incomplete", pair_id, ",".join(sorted(by_lang)))]
    fa, en = by_lang["fa"], by_lang["en"]
    out: list[GoldProblem] = []
    same = (
        ("expected_status", fa.expected_status == en.expected_status),
        ("expected_docs", fa.expected_docs == en.expected_docs),
        ("expected_outside_docs", fa.expected_outside_docs == en.expected_outside_docs),
        ("expected_escalation", fa.expected_escalation == en.expected_escalation),
        ("detail", fa.detail == en.detail),
        ("facts", len(fa.expected_facts) == len(en.expected_facts)),
        ("evidence", len(fa.evidence) == len(en.evidence)),
        ("origin", fa.origin == en.origin),
    )
    out.extend(
        GoldProblem("pair_mismatch", pair_id, name) for name, ok in same if not ok
    )
    return out


def _answered_problems(
    item: GoldItem, found: FactsFound, language_ok: LanguageCheck
) -> list[GoldProblem]:
    out: list[GoldProblem] = []
    ref = item.id
    if not item.expected_docs:
        out.append(GoldProblem("missing_docs", ref))
    if not item.expected_facts:
        out.append(GoldProblem("missing_facts", ref))
    if not item.evidence:
        out.append(GoldProblem("missing_evidence", ref))
    for e in item.evidence:
        if e.language != item.language:
            out.append(GoldProblem("evidence_language", ref, e.document_id))
        if e.document_id not in item.expected_docs:
            out.append(GoldProblem("evidence_document", ref, e.document_id))
    total = len(item.expected_facts)
    if item.evidence and found(item.quote_text, item.expected_facts)[0] != total:
        out.append(GoldProblem("fact_not_in_evidence", ref))
    if found(item.reference_answer, item.expected_facts)[0] != total:
        out.append(GoldProblem("reference_missing_fact", ref))
    labels = cited_labels(item.reference_answer)
    valid = {(e.document_id, i) for i, e in enumerate(item.evidence, 1)}
    if not labels:
        out.append(GoldProblem("reference_label", ref, "no label"))
    elif any(lab is None or lab not in valid for lab in labels):
        out.append(GoldProblem("reference_label", ref, "unknown label"))
    if language_ok(item.reference_answer, item.language) is False:
        out.append(GoldProblem("wrong_language", ref, "reference"))
    if total >= 2:
        if not item.partial_answer.strip():
            out.append(GoldProblem("partial_missing", ref))
        else:
            hit = found(item.partial_answer, item.expected_facts)[0]
            if 2 * hit > total:
                out.append(GoldProblem("partial_too_complete", ref, f"{hit}/{total}"))
            if not cited_labels(item.partial_answer):
                out.append(GoldProblem("partial_label", ref))
            if language_ok(item.partial_answer, item.language) is False:
                out.append(GoldProblem("wrong_language", ref, "partial"))
    return out


def _refusal_problems(item: GoldItem) -> list[GoldProblem]:
    out: list[GoldProblem] = []
    if item.expected_facts or item.evidence or item.expected_docs:
        out.append(GoldProblem("refusal_with_facts", item.id))
    if not item.reference_answer.lstrip().upper().startswith(REFUSAL_TOKEN):
        out.append(GoldProblem("refusal_reference", item.id))
    if item.expected_status == "out_of_scope" and not (
        item.expected_escalation and item.expected_outside_docs
    ):
        out.append(GoldProblem("escalation_missing", item.id))
    if item.detail != "refusal":
        out.append(GoldProblem("refusal_detail", item.id))
    return out


def validate_gold(
    items: Iterable[GoldItem], found: FactsFound, language_ok: LanguageCheck
) -> list[GoldProblem]:
    rows = list(items)
    out: list[GoldProblem] = []
    seen: set[str] = set()
    for item in rows:
        if item.id in seen:
            out.append(GoldProblem("duplicate_id", item.id))
        seen.add(item.id)
        if language_ok(item.question, item.language) is False:
            out.append(GoldProblem("wrong_language", item.id, "question"))
        if item.answered:
            out.extend(_answered_problems(item, found, language_ok))
        else:
            out.extend(_refusal_problems(item))
    for pair_id, by_lang in pairs(rows).items():
        out.extend(_pair_problems(pair_id, by_lang))
    return out


def phase8_coverage(
    items: Iterable[GoldItem], phase8_ids: Iterable[str]
) -> tuple[int, int, list[str]]:
    """(Phase 8 sample ids found as an origin, total, missing ids)."""
    have = {i.phase8_id for i in items if i.phase8_id}
    wanted = sorted(set(phase8_ids))
    missing = [w for w in wanted if w not in have]
    return len(wanted) - len(missing), len(wanted), missing
