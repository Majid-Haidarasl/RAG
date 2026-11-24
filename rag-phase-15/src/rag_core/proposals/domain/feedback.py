"""Automated bidder feedback: template text from the evaluation and the registry facts.

Every line is both a fact and a line of the text, so the template is grounded
by construction; the Phase 10 judges check it like a summary (ids
``(rfp_id, proposal_id)`` must appear, and the knowledge subjects
``(item, *issues)`` should be named).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rag_core.proposals.domain.evaluation import Evaluation, text
from rag_core.proposals.domain.model import ProposalRegistry
from rag_core.rfp.domain.blueprint import Blueprint

HEADINGS = {
    "result": ("Result", "نتیجه"),
    "comparison": ("Comparison", "مقایسه"),
    "notes": ("Evaluator notes", "یادداشت ارزیاب"),
    "record": ("Knowledge record", "ثبت دانش"),
}


@dataclass(frozen=True)
class FeedbackDraft:
    proposal_id: str
    rfp_id: str
    language: str
    facts: tuple[str, ...]
    text: str
    items: tuple[str, ...]
    gaps: tuple[str, ...]

    @property
    def chars(self) -> int:
        return len(self.text)

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal": self.proposal_id,
            "rfp_id": self.rfp_id,
            "language": self.language,
            "facts": list(self.facts),
            "text": self.text,
            "items": list(self.items),
            "gaps": list(self.gaps),
            "chars": self.chars,
        }


def build_feedback(
    bp: Blueprint,
    registry: ProposalRegistry,
    evaluation: Evaluation,
    proposal_id: str,
    language: str,
) -> FeedbackDraft:
    fa = language == "fa"
    p = registry.get(proposal_id)
    s = evaluation.get(proposal_id)
    if p is None or s is None:
        raise KeyError(proposal_id)
    facts: list[str] = []
    out: list[str] = []
    seen: set[str] = set()

    def add(section: str, row: str) -> None:
        if section not in seen:
            seen.add(section)
            out.append(HEADINGS[section][1 if fa else 0] + ":")
        facts.append(row)
        out.append(row)

    n = len(evaluation.ranked)
    parts = []
    for line in s.lines:
        c = bp.criterion(line.criterion_id)
        name = c.name(language) if c else line.criterion_id
        pct = c.percent if c else 0
        sign = "٪" if fa else "%"
        parts.append(
            f"{line.criterion_id} ({name}) {text(line.score)} × {pct}{sign} = {line.contribution}"
        )
    joined = "؛ ".join(parts) if fa else "; ".join(parts)
    weighted = (
        str(s.weighted) if s.weighted is not None else ("نامعلوم" if fa else "unknown")
    )
    if fa:
        add(
            "result",
            f"بازخورد پیشنهاد {p.proposal_id} ({p.label('fa')}، {p.vendor('fa')}) برای درخواست "
            f"{registry.rfp_id}، نسخه {p.version}.",
        )
        add(
            "result", f"امتیاز وزنی {weighted} از 100 = {joined}؛ رتبه {s.rank} از {n}."
        )
    else:
        add(
            "result",
            f"Feedback on proposal {p.proposal_id} ({p.label('en')}, {p.vendor('en')}) to RFP "
            f"{registry.rfp_id}, version {p.version}.",
        )
        add(
            "result",
            f"Weighted score {weighted} of 100 = {joined}; rank {s.rank} of {n}.",
        )
    w = evaluation.winner
    if w is not None:
        wp = registry.get(w.proposal_id)
        vendor = wp.vendor(language) if wp else w.proposal_id
        margin = evaluation.margin
        if w.proposal_id == p.proposal_id:
            row = (
                f"این پیشنهاد برگزیده شد؛ فاصله با رتبه بعد {margin} امتیاز."
                if fa
                else f"This proposal was selected; lead over the next one {margin} points."
            )
        else:
            gap = (
                (w.weighted - s.weighted)
                if (w.weighted is not None and s.weighted is not None)
                else None
            )
            row = (
                f"پیشنهاد برگزیده {w.proposal_id} ({vendor}) با امتیاز {w.weighted}؛ فاصله {gap} امتیاز."
                if fa
                else f"Selected proposal {w.proposal_id} ({vendor}) with {w.weighted}; gap {gap} points."
            )
        add("result", row)
    c, f = evaluation.cheapest, evaluation.fastest
    if c is not None and f is not None:
        if fa:
            add(
                "comparison",
                f"قیمت {text(p.price_mtoman)} میلیون تومان و مدت {p.duration_weeks} هفته؛ کمترین قیمت "
                f"{text(c.price)} میلیون تومان ({c.proposal_id}) و کوتاه‌ترین مدت {f.duration} هفته "
                f"({f.proposal_id}).",
            )
        else:
            add(
                "comparison",
                f"Price {text(p.price_mtoman)} million toman and duration {p.duration_weeks} weeks; "
                f"lowest price {text(c.price)} million toman ({c.proposal_id}) and shortest duration "
                f"{f.duration} weeks ({f.proposal_id}).",
            )
    if s.missing_sections:
        miss = "، ".join(s.missing_sections) if fa else ", ".join(s.missing_sections)
        add(
            "comparison",
            f"بخش‌های لازم ناقص: {miss}."
            if fa
            else f"Missing required sections: {miss}.",
        )
    if p.feedback(language):
        add(
            "notes",
            (
                f"بازخورد ثبت‌شده: {p.feedback('fa')}"
                if fa
                else f"Recorded feedback: {p.feedback('en')}"
            ),
        )
    if p.clarifications(language):
        cl = (
            "؛ ".join(p.clarifications("fa"))
            if fa
            else "; ".join(p.clarifications("en"))
        )
        add(
            "notes",
            f"پرسش‌های روشن‌سازی: {cl}." if fa else f"Clarifications requested: {cl}.",
        )
    d = registry.decision
    if d is not None and d.reason(language):
        add(
            "notes",
            f"دلیل تصمیم: {d.reason('fa')}"
            if fa
            else f"Decision reason: {d.reason('en')}",
        )
    subjects = [*([bp.item] if bp.item else []), *bp.issues]
    joined_subjects = "، ".join(subjects) if fa else ", ".join(subjects)
    add(
        "record",
        f"این نتیجه زیر {joined_subjects} در گره {bp.owner_node} ثبت می‌شود."
        if fa
        else f"This result is recorded under {joined_subjects} in node {bp.owner_node}.",
    )
    return FeedbackDraft(
        p.proposal_id,
        registry.rfp_id,
        language,
        tuple(facts),
        "\n".join(out),
        (registry.rfp_id, p.proposal_id),
        tuple(subjects),
    )
