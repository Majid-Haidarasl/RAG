"""Key-issue brief: fact lines and a deterministic template, in Persian and English.

The fact lines are the only source a brief may use (the Phase 10 judge sees
them as its FACTS block). The template is built from the same values, so
every number and identifier in it is found in the facts.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from rag_core.prioritization.domain.model import ScoredIssue
from rag_core.prioritization.domain.unblocking import NextAction

STATUS_FA = {
    "open": "باز",
    "triaged": "بررسی‌شده",
    "in_progress": "در جریان",
    "blocked": "مسدود",
    "resolved": "حل‌شده",
    "closed": "بسته",
    "reopened": "بازگشایی‌شده",
}
SEVERITY_FA = {"high": "زیاد", "medium": "متوسط", "low": "کم"}
LABELS_EN = {
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
LABELS_FA = {
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
MAX_GAPS = 6
MAX_RESEARCH = 2


@dataclass(frozen=True)
class BriefGap:
    gap_id: str
    subject: str
    severity: str
    title_en: str
    title_fa: str
    issue_id: str = ""


@dataclass(frozen=True)
class KeyIssueBrief:
    cycle_id: str
    cutoff: str
    language: str
    facts: tuple[str, ...]
    text: str
    items: tuple[str, ...]  # key issue ids the brief must name
    gaps: tuple[str, ...]  # gap subjects the brief should name
    candidates: tuple[str, ...] = ()  # every ranked (open) issue id
    lines: dict[str, list[str]] = field(default_factory=dict)

    @property
    def words(self) -> int:
        return len(self.text.split())


def num(value: float) -> str:
    """12.0 -> 12, 11.25 -> 11.25 (same text in facts and template)."""
    return f"{value:g}" if isinstance(value, float) else str(value)


def _factors(s: ScoredIssue, language: str) -> str:
    labels = LABELS_FA if language == "fa" else LABELS_EN
    sep = "، " if language == "fa" else ", "
    return sep.join(f"{labels[k]} {num(v)}" for k, v in s.top_factors(3))


def build_brief(
    cycle_id: str,
    cutoff: str,
    key: list[ScoredIssue],
    gaps: Iterable[BriefGap],
    research: Iterable[BriefGap],
    actions: dict[str, list[NextAction]],
    language: str,
    candidates: tuple[str, ...] = (),
) -> KeyIssueBrief:
    fa = language == "fa"
    key_ids = [s.issue_id for s in key]
    gap_list = [g for g in gaps if g.issue_id in key_ids][:MAX_GAPS]
    research_list = list(research)[:MAX_RESEARCH]
    facts: list[str] = []
    text: list[str] = []
    if fa:
        head = f"چرخه {cycle_id}، مقطع گزارش {cutoff}."
        facts.append(head)
        text.append(f"مسئله‌های کلیدی چرخه {cycle_id} (مقطع {cutoff}):")
    else:
        head = f"Cycle {cycle_id}, reporting cutoff {cutoff}."
        facts.append(head)
        text.append(f"Key issues of cycle {cycle_id} (cutoff {cutoff}):")
    for s in key:
        sig = s.signal
        status = sig.status if sig else ""
        progress = sig.progress if sig else None
        money = sig.exposure_mtoman if sig else 0
        title = s.title_fa if fa and s.title_fa else s.title_en
        factors = _factors(s, language)
        if fa:
            facts.append(
                f"مسئله کلیدی {s.rank}: {s.issue_id} — {title}. وضعیت {STATUS_FA.get(status, status)}. "
                f"امتیاز {num(s.score)} از 100."
            )
            facts.append(f"عوامل اصلی {s.issue_id}: {factors}.")
            line = (
                f"{s.rank}. {s.issue_id} ({title}): امتیاز {num(s.score)} از 100، وضعیت {STATUS_FA.get(status, status)}؛ "
                f"عوامل اصلی: {factors}."
            )
            if progress is not None:
                facts.append(f"پیشرفت {s.issue_id}: {progress}٪.")
                line += f" پیشرفت {progress}٪."
            if money:
                facts.append(f"مبلغ در خطر {s.issue_id}: {money} میلیون تومان.")
                line += f" مبلغ در خطر {money} میلیون تومان."
        else:
            facts.append(
                f"Key issue {s.rank}: {s.issue_id} — {title}. Status {status}. Score {num(s.score)} of 100."
            )
            facts.append(f"{s.issue_id} main factors: {factors}.")
            line = (
                f"{s.rank}. {s.issue_id} ({title}): score {num(s.score)} of 100, status {status}; "
                f"main factors: {factors}."
            )
            if progress is not None:
                facts.append(f"{s.issue_id} progress: {progress}%.")
                line += f" Progress {progress}%."
            if money:
                facts.append(f"{s.issue_id} money at stake: {money} million toman.")
                line += f" Money at stake {money} million toman."
        text.append(line)
    for g in gap_list:
        if fa:
            row = f"شکاف {g.gap_id} (شدت {SEVERITY_FA.get(g.severity, g.severity)}): {g.title_fa}."
        else:
            row = f"Gap {g.gap_id} ({g.severity}): {g.title_en}."
        facts.append(row)
        text.append(row)
    for issue_id in key_ids:
        for a in actions.get(issue_id, [])[:1]:
            if fa:
                row = f"اقدام بعدی برای {issue_id}: {a.item_id} که {', '.join(a.unblocks)} را آزاد می‌کند."
            else:
                row = f"Next action for {issue_id}: {a.item_id}, which unblocks {', '.join(a.unblocks)}."
            facts.append(row)
            text.append(row)
    for r in research_list:
        row = (
            f"شکاف پژوهشی {r.subject}: {r.title_fa}."
            if fa
            else f"Research gap {r.subject}: {r.title_en}."
        )
        facts.append(row)
        text.append(row)
    subjects = tuple(
        dict.fromkeys(
            [*(g.subject for g in gap_list), *(r.subject for r in research_list)]
        )
    )
    return KeyIssueBrief(
        cycle_id,
        cutoff,
        language,
        tuple(facts),
        "\n".join(text),
        tuple(key_ids),
        subjects,
        tuple(candidates),
    )
