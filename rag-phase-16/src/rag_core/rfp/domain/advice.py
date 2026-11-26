"""AI advice on an RFP or a bidder feedback (qwen3:8b, think off, JSON reply). Advice only.

The model gets the fact lines and returns one JSON object. The text is accepted
only when every number and identifier is found in the facts (shared-kernel
``FactValidator``), it invents no RFP, issue, proposal, requirement or
criterion id, and the judges accept it (Phase 10 combined rule). The template
RFP and the template feedback never change.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.fact_ports import FactValidator, FactVerdict
from rag_core.shared_kernel.numerals import normalize_digits

_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")
ID_RE = re.compile(
    r"\b(?:AR-[A-Z]{2,5}-\d{2,4}(?:-\d{2,4})?(?:/[A-Z0-9]+)?|PRP-[A-Z]+|REQ-[A-Z]+|CRT-[A-Z]+|LNK-[A-Z]+)\b"
)


class ReplyParseError(InvariantError):
    pass


def ids_in(texts: Iterable[str]) -> set[str]:
    out: set[str] = set()
    for t in texts:
        out.update(ID_RE.findall(normalize_digits(t or "").upper()))
    return out


@dataclass(frozen=True)
class ParsedReply:
    text: str
    questions: tuple[str, ...]
    mode: str  # json | json_extracted


def parse_reply(raw: str, key: str) -> ParsedReply:
    text = _FENCE_RE.sub("", (raw or "").strip()).strip()
    if not text:
        raise ReplyParseError("empty reply")
    mode = "json"
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise ReplyParseError("no JSON object in the reply") from None
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ReplyParseError(f"invalid JSON: {exc.msg}") from None
        mode = "json_extracted"
    if not isinstance(data, dict):
        raise ReplyParseError("the reply must be a JSON object")
    body = data.get(key)
    if not isinstance(body, str) or not body.strip():
        raise ReplyParseError(f"'{key}' is missing or empty")
    questions = data.get("questions") or []
    if isinstance(questions, str):
        questions = [questions]
    if not isinstance(questions, list):
        raise ReplyParseError("'questions' must be a list")
    return ParsedReply(
        body.strip(), tuple(str(q).strip() for q in questions if str(q).strip()), mode
    )


@dataclass(frozen=True)
class ReplyCheck:
    grounded: bool
    unsupported: tuple[str, ...]
    invented_ids: tuple[str, ...]
    mentioned: int
    expected: int

    @property
    def ok(self) -> bool:
        return self.grounded and not self.invented_ids

    def to_dict(self) -> dict[str, Any]:
        return {
            "grounded": self.grounded,
            "unsupported": list(self.unsupported),
            "invented_ids": list(self.invented_ids),
            "mentioned": self.mentioned,
            "expected": self.expected,
            "ok": self.ok,
        }


def check_reply(
    parsed: ParsedReply,
    facts: Iterable[str],
    items: Iterable[str],
    validator: FactValidator,
) -> ReplyCheck:
    facts = list(facts)
    items = tuple(items)
    body = " ".join([parsed.text, *parsed.questions])
    report = validator.validate(body, facts)
    unsupported = tuple(
        r.claim.raw_text
        for r in report.results
        if r.verdict in {FactVerdict.UNSUPPORTED, FactVerdict.FLAGGED}
    )
    known = ids_in(facts) | {i.upper() for i in items}
    invented = tuple(
        sorted(
            i
            for i in ids_in([body])
            if i not in known and i.split("/", 1)[0] not in known
        )
    )
    upper = normalize_digits(parsed.text).upper()
    mentioned = sum(1 for i in items if i.upper() in upper)
    return ReplyCheck(not unsupported, unsupported, invented, mentioned, len(items))


@dataclass
class AiReply:
    task: str  # rfp_summary | feedback
    subject: str  # RFP id or proposal id
    language: str
    status: str = "error"  # accepted | rejected | error
    raw: str = ""
    parsed: ParsedReply | None = None
    check: ReplyCheck | None = None
    error: str = ""
    verdicts: list[dict[str, Any]] = field(default_factory=list)
    seconds: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "subject": self.subject,
            "language": self.language,
            "status": self.status,
            "text": self.parsed.text if self.parsed else "",
            "questions": list(self.parsed.questions) if self.parsed else [],
            "parse_mode": self.parsed.mode if self.parsed else "error",
            "check": self.check.to_dict() if self.check else None,
            "error": self.error,
            "verdicts": list(self.verdicts),
            "raw": self.raw,
            "seconds": round(self.seconds, 3),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
        }
