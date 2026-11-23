"""Required identifiers in AI texts (Phases 11-13 finding: replies dropped ids).

Three prompt variants are compared on the same jobs:

* ``baseline``     — the Phase 13 prompt (ids listed inline in one sentence);
* ``listed``       — the ids as a numbered checklist before the facts;
* ``listed_retry`` — ``listed`` plus one retry that names the missing ids;
* ``listed_guarded`` — ``listed_retry`` plus an invented-id guard (Phase 15): a text
  that uses an id outside the allowed set is retried with a note naming the
  invented ids, the clean text wins over a text with more ids, and a text that
  still invents an id is rejected.

An id counts as mentioned when it occurs in the text exactly (case-insensitive,
Persian digits read as Latin). ``KL:AR-ISS-024/WEB`` is mentioned by the text
``KL:AR-ISS-024/WEB`` only, not by ``AR-ISS-024``.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from rag_core.shared_kernel.numerals import normalize_digits


class IdVariant(StrEnum):
    BASELINE = "baseline"
    LISTED = "listed"
    LISTED_RETRY = "listed_retry"
    LISTED_GUARDED = "listed_guarded"


RETRY_VARIANTS = frozenset({IdVariant.LISTED_RETRY.value, IdVariant.LISTED_GUARDED.value})
LISTED_VARIANTS = frozenset({IdVariant.LISTED.value, *RETRY_VARIANTS})


def required_ids(items: Iterable[str], gaps: Iterable[str] = ()) -> tuple[str, ...]:
    return tuple(dict.fromkeys(i.strip() for i in [*items, *gaps] if i and i.strip()))


def mentioned(text: str, identifier: str) -> bool:
    return identifier.upper() in normalize_digits(text or "").upper()


def missing_ids(text: str, required: Sequence[str]) -> tuple[str, ...]:
    return tuple(i for i in required if not mentioned(text, i))


def mention_count(text: str, required: Sequence[str]) -> tuple[int, int]:
    return len(required) - len(missing_ids(text, required)), len(required)


def id_checklist(required: Sequence[str]) -> str:
    """Numbered lines, one id per line: ``1. AR-RFP-1403-07``."""
    return "\n".join(f"{i}. {r}" for i, r in enumerate(required, 1))


def retry_note(missing: Sequence[str], language: str) -> str:
    ids = ", ".join(missing)
    if language == "fa":
        return (f"در پاسخ قبلی این شناسه‌ها نیامده بود: {ids}. همان شیء JSON را دوباره بنویس و هر شناسهٔ الزامی را "
                "دقیقاً به همان شکل در متن بیاور. عدد یا شناسهٔ تازه‌ای اضافه نکن.")
    return (f"Your previous reply did not name these ids: {ids}. Write the same JSON object again and put every "
            "required id in the text exactly as listed. Do not add new numbers or ids.")


def guard_note(missing: Sequence[str], invented: Sequence[str], allowed: Sequence[str], language: str) -> str:
    """Retry note of ``listed_guarded``: drop the invented ids, keep to the allowed list, add the missing ones."""
    allowed_text = ", ".join(allowed) or "-"
    parts: list[str] = []
    if language == "fa":
        if invented:
            parts.append(f"در پاسخ قبلی این شناسه‌ها در فهرست مجاز نبودند و باید حذف شوند: {', '.join(invented)}.")
        if missing:
            parts.append(f"این شناسه‌های الزامی نیامده بود: {', '.join(missing)}.")
        parts.append(f"فقط این شناسه‌ها مجازند: {allowed_text}. همان شیء JSON را دوباره بنویس و عدد یا شناسهٔ تازه‌ای "
                     "اضافه نکن.")
        return " ".join(parts)
    if invented:
        parts.append(f"Your previous reply used ids that are not allowed; remove them: {', '.join(invented)}.")
    if missing:
        parts.append(f"It did not name these required ids: {', '.join(missing)}.")
    parts.append(f"Only these ids are allowed: {allowed_text}. Write the same JSON object again and do not add new "
                 "numbers or ids.")
    return " ".join(parts)


def guard_rank(error: str, invented: Sequence[str], missing: Sequence[str]) -> tuple[int, int, int]:
    """Lower is better: a parsed text first, then fewer invented ids, then fewer missing ids."""
    return (1 if error else 0, len(invented), len(missing))


@dataclass(frozen=True)
class IdRun:
    task: str
    subject: str
    language: str
    variant: str
    mentioned: int
    expected: int
    grounded: bool
    invented: tuple[str, ...]
    accepted: bool
    attempts: int = 1
    seconds: float = 0.0
    error: str = ""
    rule_total: int | None = None

    @property
    def all_ids(self) -> bool:
        return self.expected > 0 and self.mentioned == self.expected

    def to_dict(self) -> dict[str, object]:
        return {"task": self.task, "subject": self.subject, "language": self.language, "variant": self.variant,
                "mentioned": f"{self.mentioned}/{self.expected}", "all_ids": self.all_ids, "grounded": self.grounded,
                "invented": list(self.invented), "accepted": self.accepted, "attempts": self.attempts,
                "seconds": round(self.seconds, 3), "error": self.error, "rule_total": self.rule_total}


def summarize_id_runs(rows: Iterable[IdRun]) -> dict[str, dict[str, object]]:
    by: dict[str, list[IdRun]] = {}
    for r in rows:
        by.setdefault(r.variant, []).append(r)
    out: dict[str, dict[str, object]] = {}
    for variant, runs in by.items():
        n = len(runs)
        hit = sum(r.mentioned for r in runs)
        total = sum(r.expected for r in runs)
        out[variant] = {
            "n": n,
            "errors": sum(1 for r in runs if r.error),
            "mention_rate": round(hit / total, 3) if total else None,
            "mentioned": f"{hit}/{total}",
            "all_ids": sum(1 for r in runs if r.all_ids),
            "grounded": sum(1 for r in runs if r.grounded),
            "invented_ids": sum(len(r.invented) for r in runs),
            "accepted": sum(1 for r in runs if r.accepted),
            "accept_rate": round(sum(1 for r in runs if r.accepted) / n, 3) if n else None,
            "retries": sum(r.attempts - 1 for r in runs),
            "seconds_avg": round(sum(r.seconds for r in runs) / n, 3) if n else None,
        }
    return out
