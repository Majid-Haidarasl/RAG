"""AI key-issue brief (qwen3:8b, think off, JSON reply). Advice only.

The local model gets the brief facts and returns:

* ``brief`` — a short text for the chief executive, in Persian or English;
* ``order`` — the key issue ids in the order it would handle them.

The deterministic ranking never changes. The AI brief is accepted only when
its numbers and identifiers are found in the facts (shared-kernel
``FactValidator``), every id in ``order`` is a ranked issue, and — when
judges are used — the brief passes them (Phase 10 combined rule).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from rag_core.prioritization.domain.brief import KeyIssueBrief
from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.fact_ports import FactValidator, FactVerdict
from rag_core.shared_kernel.numerals import normalize_digits

_ISSUE_RE = re.compile(r"AR-ISS-\d{3}")
_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")

SYSTEM_EN = (
    "You help the ArmanRayan chief executive decide which organizational issues to handle first. "
    "Use only the facts you are given. Copy identifiers such as AR-ISS-024 and AR-ISS-024/HW exactly. "
    "Do not add numbers, dates, amounts, people or documents that are not in the facts. "
    "Reply with one JSON object only."
)
SYSTEM_FA = (
    "تو به مدیرعامل آرمان‌رایان کمک می‌کنی تصمیم بگیرد کدام مسئله‌های سازمانی را اول رسیدگی کند. "
    "فقط از واقعیت‌های داده‌شده استفاده کن. شناسه‌هایی مثل AR-ISS-024 و AR-ISS-024/HW را دقیقاً همان‌طور بنویس. "
    "هیچ عدد، تاریخ، مبلغ، شخص یا سندی را که در واقعیت‌ها نیست اضافه نکن. فقط یک شیء JSON برگردان."
)


class AdviceParseError(InvariantError):
    pass


def advice_prompt(brief: KeyIssueBrief) -> tuple[str, str]:
    block = "\n".join(brief.facts)
    ids = ", ".join(brief.items) or "none"
    if brief.language == "fa":
        user = (
            f"واقعیت‌ها:\n{block}\n\n"
            f"مسئله‌های کلیدی: {ids}.\n"
            'یک شیء JSON با این کلیدها برگردان: "brief" (خلاصهٔ فارسی حداکثر ۶ جمله برای مدیرعامل، بدون جدول؛ '
            'هر مسئلهٔ کلیدی را با شناسه‌اش نام ببر و شکاف‌های مهم را بگو)، "order" (فهرست شناسهٔ مسئله‌های کلیدی '
            "به ترتیبی که باید رسیدگی شوند)."
        )
        return SYSTEM_FA, user
    user = (
        f"Facts:\n{block}\n\n"
        f"Key issues: {ids}.\n"
        'Return one JSON object with these keys: "brief" (an English brief for the chief executive in at most '
        '6 sentences, no tables; name every key issue by its id and mention the important gaps), "order" (list of '
        "the key issue ids in the order they should be handled)."
    )
    return SYSTEM_EN, user


@dataclass(frozen=True)
class ParsedAdvice:
    brief: str
    order: tuple[str, ...]
    mode: str  # json | json_extracted


def _ids(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        parts = [value]
    elif isinstance(value, list):
        parts = [str(v) for v in value]
    else:
        raise AdviceParseError("'order' must be a list of ids")
    found: list[str] = []
    for part in parts:
        found.extend(_ISSUE_RE.findall(normalize_digits(part).upper()))
    return tuple(dict.fromkeys(found))


def parse_advice(raw: str) -> ParsedAdvice:
    text = _FENCE_RE.sub("", (raw or "").strip()).strip()
    if not text:
        raise AdviceParseError("empty reply")
    mode = "json"
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise AdviceParseError("no JSON object in the reply") from None
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise AdviceParseError(f"invalid JSON: {exc.msg}") from None
        mode = "json_extracted"
    if not isinstance(data, dict):
        raise AdviceParseError("the reply must be a JSON object")
    brief = data.get("brief")
    if not isinstance(brief, str) or not brief.strip():
        raise AdviceParseError("'brief' is missing or empty")
    return ParsedAdvice(brief.strip(), _ids(data.get("order")), mode)


@dataclass(frozen=True)
class AdviceCheck:
    grounded: bool
    unsupported: tuple[str, ...]
    invented_ids: tuple[str, ...]
    same_top: bool
    mentioned: int

    @property
    def ok(self) -> bool:
        return self.grounded and not self.invented_ids

    def to_dict(self) -> dict[str, Any]:
        return {
            "grounded": self.grounded,
            "unsupported": list(self.unsupported),
            "invented_ids": list(self.invented_ids),
            "same_top": self.same_top,
            "mentioned": self.mentioned,
            "ok": self.ok,
        }


def check_advice(
    parsed: ParsedAdvice, brief: KeyIssueBrief, validator: FactValidator
) -> AdviceCheck:
    report = validator.validate(parsed.brief, list(brief.facts))
    unsupported = tuple(
        r.claim.raw_text
        for r in report.results
        if r.verdict in {FactVerdict.UNSUPPORTED, FactVerdict.FLAGGED}
    )
    known = set(brief.candidates) | set(brief.items)
    text_ids = set(_ISSUE_RE.findall(normalize_digits(parsed.brief).upper()))
    invented = tuple(sorted({i for i in [*parsed.order, *text_ids] if i not in known}))
    same_top = (
        bool(parsed.order) and bool(brief.items) and parsed.order[0] == brief.items[0]
    )
    mentioned = sum(
        1 for i in brief.items if i in normalize_digits(parsed.brief).upper()
    )
    return AdviceCheck(not unsupported, unsupported, invented, same_top, mentioned)


@dataclass
class AiBrief:
    language: str
    status: str  # accepted | rejected | error
    raw: str = ""
    parsed: ParsedAdvice | None = None
    check: AdviceCheck | None = None
    error: str = ""
    verdicts: list[dict[str, Any]] = field(default_factory=list)
    seconds: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "status": self.status,
            "brief": self.parsed.brief if self.parsed else "",
            "order": list(self.parsed.order) if self.parsed else [],
            "parse_mode": self.parsed.mode if self.parsed else "error",
            "check": self.check.to_dict() if self.check else None,
            "error": self.error,
            "verdicts": list(self.verdicts),
            "raw": self.raw,
            "seconds": round(self.seconds, 3),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
        }
