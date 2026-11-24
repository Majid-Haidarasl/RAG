"""AI transfer suggestions (qwen3:8b, think off, JSON reply).

For one drafted package the local model gets the package facts and returns:

* ``summary`` — a short text for the receiving layer, in Persian or English;
* ``raise``   — item ids the receiver should act on first (it may name an
  item that the detail-level limit left out: an *addition*);
* ``reason``  — one sentence why.

A suggestion is advice. It never changes the deterministic package. It is
accepted only when the summary and the reason are grounded in the facts (same
``FactValidator`` as Phase 9), every raised id is a real candidate id, and —
when a judge is used — the summary passes the judge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import Any

from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.fact_ports import FactValidator
from rag_core.shared_kernel.numerals import normalize_digits
from rag_core.transfer.domain.builder import PackageDraft
from rag_core.transfer.domain.review import GroundingCheck, ground

_ID_RE = re.compile(r"AR-ISS-\d{3}(?:/[A-Z0-9]+)?")
_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")
MAX_SENTENCES = {
    "executive": 4,
    "managerial": 6,
    "technical_summary": 8,
    "detailed_technical": 10,
}

SYSTEM_EN = (
    "You advise ArmanRayan managers on what a team or deputy should pass upward in its periodic knowledge-transfer "
    "package. Use only the facts you are given. Copy identifiers such as AR-ISS-024/HW, AR-HW-012 and N-HW-REP "
    "exactly. Do not add numbers, dates, amounts, people or documents that are not in the facts. "
    "Reply with one JSON object only."
)
SYSTEM_FA = (
    "تو به مدیران آرمان‌رایان پیشنهاد می‌دهی که یک تیم یا معاونت در بستهٔ دوره‌ای انتقال دانش چه چیزی را به لایهٔ بالاتر "
    "بفرستد. فقط از واقعیت‌های داده‌شده استفاده کن. شناسه‌هایی مثل AR-ISS-024/HW و AR-HW-012 و N-HW-REP را دقیقاً "
    "همان‌طور بنویس. هیچ عدد، تاریخ، مبلغ، شخص یا سندی را که در واقعیت‌ها نیست اضافه نکن. فقط یک شیء JSON برگردان."
)
AUDIENCE_EN = {
    "executive": "the Board of Directors (strategic risks and decisions only)",
    "managerial": "the chief executive (issue status, cost/time impact and pending decisions)",
    "technical_summary": "the deputy (dependencies, risks, capacity needs and technical decisions)",
    "detailed_technical": "the execution team (full technical detail)",
}
AUDIENCE_FA = {
    "executive": "هیئت‌مدیره (فقط ریسک‌های راهبردی و تصمیم‌ها)",
    "managerial": "مدیرعامل (وضعیت مسئله‌ها، اثر هزینه و زمان و تصمیم‌های معوق)",
    "technical_summary": "معاون (وابستگی‌ها، ریسک‌ها، نیاز ظرفیت و تصمیم‌های فنی)",
    "detailed_technical": "تیم اجرا (جزئیات کامل فنی)",
}


class SuggestionParseError(InvariantError):
    pass


def candidate_ids(draft: PackageDraft) -> tuple[str, ...]:
    """Items the model may raise: the included items and the omitted ones."""
    return tuple(dict.fromkeys([*(i.item_id for i in draft.items), *draft.omitted]))


def suggestion_prompt(draft: PackageDraft, language: str) -> tuple[str, str]:
    block = "\n".join(draft.facts)
    ids = ", ".join(candidate_ids(draft)) or "none"
    level = draft.detail_level
    sentences = MAX_SENTENCES.get(level, 6)
    if language == "fa":
        user = (
            f"واقعیت‌ها:\n{block}\n\n"
            f"گیرنده: {AUDIENCE_FA.get(level, level)}. شناسه‌های قابل انتخاب: {ids}.\n"
            f'یک شیء JSON با این کلیدها برگردان: "summary" (خلاصهٔ فارسی حداکثر {sentences} جمله برای گیرنده، '
            'بدون جدول)، "raise" (فهرست شناسه‌هایی که گیرنده باید اول به آن‌ها رسیدگی کند؛ فقط از شناسه‌های '
            'قابل انتخاب)، "reason" (یک جملهٔ فارسی دربارهٔ دلیل).'
        )
        return SYSTEM_FA, user
    user = (
        f"Facts:\n{block}\n\n"
        f"Receiver: {AUDIENCE_EN.get(level, level)}. Selectable ids: {ids}.\n"
        f'Return one JSON object with these keys: "summary" (an English summary for the receiver in at most '
        f'{sentences} sentences, no tables), "raise" (list of ids the receiver should act on first; only selectable '
        'ids), "reason" (one English sentence why).'
    )
    return SYSTEM_EN, user


@dataclass(frozen=True)
class ParsedSuggestion:
    summary: str
    raise_ids: tuple[str, ...]
    reason: str
    mode: str  # json | json_extracted


def _ids(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        parts = [value]
    elif isinstance(value, list):
        parts = [str(v) for v in value]
    else:
        raise SuggestionParseError("'raise' must be a list of ids")
    found: list[str] = []
    for part in parts:
        found.extend(_ID_RE.findall(normalize_digits(part).upper()))
    return tuple(dict.fromkeys(found))


def parse_suggestion(raw: str) -> ParsedSuggestion:
    text = _FENCE_RE.sub("", (raw or "").strip()).strip()
    if not text:
        raise SuggestionParseError("empty reply")
    mode = "json"
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise SuggestionParseError("no JSON object in the reply") from None
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise SuggestionParseError(f"invalid JSON: {exc.msg}") from None
        mode = "json_extracted"
    if not isinstance(data, dict):
        raise SuggestionParseError("the reply must be a JSON object")
    summary = data.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise SuggestionParseError("'summary' is missing or empty")
    reason = data.get("reason", "")
    if not isinstance(reason, str):
        reason = str(reason)
    return ParsedSuggestion(
        summary.strip(), _ids(data.get("raise")), reason.strip(), mode
    )


@dataclass(frozen=True)
class SuggestionCheck:
    grounding: GroundingCheck
    invented_ids: tuple[str, ...]
    additions: tuple[str, ...]  # raised ids that the deterministic package left out
    known_raise: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.grounding.grounded and not self.invented_ids

    def to_dict(self) -> dict[str, Any]:
        return {
            "grounding": self.grounding.to_dict(),
            "invented_ids": list(self.invented_ids),
            "additions": list(self.additions),
            "known_raise": list(self.known_raise),
            "ok": self.ok,
        }


def check_suggestion(
    parsed: ParsedSuggestion, draft: PackageDraft, validator: FactValidator
) -> SuggestionCheck:
    text = parsed.summary + ("\n" + parsed.reason if parsed.reason else "")
    grounding = ground(text, draft.facts, validator)
    candidates = set(candidate_ids(draft))
    included = {i.item_id for i in draft.items}
    invented = tuple(i for i in parsed.raise_ids if i not in candidates)
    known = tuple(i for i in parsed.raise_ids if i in candidates)
    additions = tuple(i for i in known if i not in included)
    return SuggestionCheck(grounding, invented, additions, known)


@dataclass
class TransferSuggestion:
    cycle_id: str
    source_node: str
    target_node: str
    language: str
    status: str  # accepted | rejected | error
    raw: str = ""
    parsed: ParsedSuggestion | None = None
    check: SuggestionCheck | None = None
    error: str = ""
    verdicts: list[dict[str, Any]] = field(default_factory=list)
    seconds: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def summary(self) -> str:
        return self.parsed.summary if self.parsed else ""

    def content_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "source_node": self.source_node,
            "target_node": self.target_node,
            "language": self.language,
            "status": self.status,
            "summary": self.summary,
            "raise": list(self.parsed.raise_ids) if self.parsed else [],
            "reason": self.parsed.reason if self.parsed else "",
            "parse_mode": self.parsed.mode if self.parsed else "error",
            "check": self.check.to_dict() if self.check else None,
            "error": self.error,
            "verdicts": list(self.verdicts),
        }

    def to_dict(self) -> dict[str, Any]:
        data = self.content_dict()
        data.update(
            raw=self.raw,
            seconds=round(self.seconds, 3),
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
        )
        return data
