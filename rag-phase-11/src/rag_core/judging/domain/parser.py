"""Robust parser for LLM judge replies.

Order of attempts (the first one that yields at least one criterion wins):

1. ``json``          — the whole reply is a JSON object;
2. ``json_extracted``— the first balanced ``{...}`` object inside prose,
   code fences or ``<think>`` text;
3. ``json_repaired`` — the same object after light repairs: trailing commas,
   single quotes, unquoted keys, Python ``True/False/None``, a reply cut off
   before its closing braces;
4. ``key_value``     — lines such as ``grounding: 4/5`` or ``citation = 3``.

Accepted shapes: ``{"scores": {"grounding": 4}}``, ``{"scores": {"grounding":
{"score": 4, "reason": "..."}}}``, ``{"grounding": 4, ...}`` and
``{"scores": [{"criterion": "grounding", "score": 4}]}``. Keys are matched
through the rubric aliases (``groundedness`` → ``grounding``).

Values: integers, floats (rounded half up), strings such as ``"4"``,
``"۴"``, ``"4/5"`` (a fraction on another scale is rescaled to the
criterion maximum). Values below 0 or above the maximum are clamped and
reported. A criterion that is absent or not numeric is listed in
``missing``; the acceptance policy then rejects. A reply with no usable
score at all raises ``JudgeParseError`` (Phase 3: not a score of 0).
A total written by the judge is ignored; the total is recomputed and a
mismatch is reported as a warning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
import re
from typing import Any

from rag_core.judging.domain.model import JudgeParseError
from rag_core.judging.domain.rubric import Rubric
from rag_core.shared_kernel.numerals import normalize_digits

_THINK_RE = re.compile(r"<think>.*?</think>", re.S | re.I)
_FENCE_RE = re.compile(r"```[a-zA-Z]*")
_NUMBER_RE = re.compile(r"^\s*([-+]?\d+(?:\.\d+)?)\s*(?:(?:/|out of|of)\s*(\d+(?:\.\d+)?))?", re.I)
_CONTAINER_KEYS = ("scores", "criteria", "rubric", "evaluation", "ratings")
_VALUE_KEYS = ("score", "points", "value", "rating")
_NAME_KEYS = ("criterion", "name", "key", "id")
_TOTAL_KEYS = ("total", "total_score", "overall", "score")
_ISSUE_KEYS = ("issues", "problems", "errors", "notes")
_MAX_ISSUES = 10


@dataclass(frozen=True)
class ParsedJudgement:
    scores: dict[str, int]
    mode: str
    warnings: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()
    reported_total: float | None = None
    raw_values: dict[str, object] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return sum(self.scores.values())

    @property
    def complete(self) -> bool:
        return not self.missing

    def to_dict(self) -> dict[str, object]:
        return {"scores": dict(self.scores), "total": self.total, "mode": self.mode, "warnings": list(self.warnings),
                "missing": list(self.missing), "issues": list(self.issues), "reported_total": self.reported_total}


def strip_wrappers(raw: str) -> str:
    """Remove ``<think>`` blocks, code fences and Persian / Arabic-Indic digits."""
    text = _THINK_RE.sub(" ", raw or "")
    if "</think>" in text:
        text = text.split("</think>", 1)[1]
    text = text.replace("<think>", " ")
    text = _FENCE_RE.sub(" ", text)
    return normalize_digits(text).replace("٫", ".")


def json_objects(text: str) -> list[str]:
    """Top-level balanced ``{...}`` spans. An unterminated last object (a reply cut
    off by ``num_predict``) is closed: open string, then open ``[`` / ``{`` in reverse."""
    out: list[str] = []
    i, n = 0, len(text)
    closing = {"{": "}", "[": "]"}
    while i < n:
        if text[i] != "{":
            i += 1
            continue
        stack: list[str] = []
        in_str = False
        esc = False
        quote = ""
        end = -1
        for j in range(i, n):
            ch = text[j]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == quote:
                    in_str = False
                continue
            if ch in "\"'":
                in_str, quote = True, ch
            elif ch in "{[":
                stack.append(ch)
            elif ch in "}]":
                if stack:
                    stack.pop()
                if not stack:
                    end = j
                    break
        if end < 0:
            tail = (quote if in_str else "") + "".join(closing[c] for c in reversed(stack))
            out.append(text[i:] + tail)
            break
        out.append(text[i:end + 1])
        i = end + 1
    return out


def repair_json(candidate: str) -> str:
    s = candidate
    if '"' not in s:
        s = s.replace("'", '"')
    s = re.sub(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_\- ]*?)\s*:", r'\1"\2":', s)
    s = re.sub(r",\s*([}\]])", r"\1", s)
    s = re.sub(r"\bTrue\b", "true", s)
    s = re.sub(r"\bFalse\b", "false", s)
    s = re.sub(r"\bNone\b", "null", s)
    return s


def round_half_up(value: float) -> int:
    return int(math.floor(value + 0.5))


class JudgeOutputParser:
    def __init__(self, rubric: Rubric) -> None:
        self.rubric = rubric

    # -- public ------------------------------------------------------------------
    def parse(self, raw: str) -> ParsedJudgement:
        if raw is None or not str(raw).strip():
            raise JudgeParseError("empty judge output")
        text = strip_wrappers(str(raw)).strip()
        attempts: list[tuple[str, str]] = [("json", text)]
        objects = json_objects(text)
        attempts += [("json_extracted", o) for o in objects]
        attempts += [("json_repaired", repair_json(o)) for o in objects]
        for mode, candidate in attempts:
            try:
                payload = json.loads(candidate)
            except (json.JSONDecodeError, ValueError):
                continue
            if not isinstance(payload, dict):
                continue
            parsed = self._from_mapping(payload, mode)
            if parsed is not None:
                return parsed
        parsed = self._from_key_values(text)
        if parsed is not None:
            return parsed
        raise JudgeParseError("no criterion scores found in judge output")

    # -- JSON ----------------------------------------------------------------------
    def _from_mapping(self, payload: dict[str, Any], mode: str) -> ParsedJudgement | None:
        container: Any = payload
        for key in _CONTAINER_KEYS:
            value = payload.get(key)
            if isinstance(value, (dict, list)) and value:
                container = value
                break
        pairs: list[tuple[str, Any]] = []
        if isinstance(container, list):
            for item in container:
                if not isinstance(item, dict):
                    continue
                name = next((item[k] for k in _NAME_KEYS if isinstance(item.get(k), str)), None)
                value = next((item[k] for k in _VALUE_KEYS if k in item), None)
                if name is not None:
                    pairs.append((name, value))
        else:
            pairs = list(container.items())
        found = [(self.rubric.resolve(k), k, v) for k, v in pairs]
        if not any(key for key, _, _ in found):
            return None
        reported = None
        for key in _TOTAL_KEYS:
            if key in payload and self.rubric.resolve(key) is None:
                number = self._number(payload[key])
                if number is not None:
                    reported = number[0]
                    break
        issues: list[str] = []
        for key in _ISSUE_KEYS:
            value = payload.get(key)
            if isinstance(value, list):
                issues = [str(v)[:200] for v in value if str(v).strip()][:_MAX_ISSUES]
                break
            if isinstance(value, str) and value.strip():
                issues = [value.strip()[:200]]
                break
        return self._build(found, mode, reported, issues)

    # -- plain text ------------------------------------------------------------------
    def _from_key_values(self, text: str) -> ParsedJudgement | None:
        found: list[tuple[str | None, str, Any]] = []
        for c in self.rubric.criteria:
            names = "|".join(re.escape(n).replace("_", r"[\s_\-]?") for n in sorted(c.names, key=len, reverse=True))
            pattern = re.compile(
                rf"(?<![A-Za-z])(?:{names})(?![A-Za-z])[\"'*\s]*[:=]\s*[\"'*]*\s*"
                rf"([-+]?\d+(?:\.\d+)?(?:\s*(?:/|out of)\s*\d+(?:\.\d+)?)?)",
                re.I,
            )
            m = pattern.search(text)
            if m:
                found.append((c.key, c.key, m.group(1)))
        if not found:
            return None
        return self._build(found, "key_value", None, [])

    # -- shared ----------------------------------------------------------------------
    @staticmethod
    def _number(value: Any) -> tuple[float, float | None] | None:
        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, (int, float)):
            return (float(value), None) if math.isfinite(float(value)) else None
        if isinstance(value, str):
            m = _NUMBER_RE.match(normalize_digits(value).replace("٫", "."))
            if not m:
                return None
            den = float(m.group(2)) if m.group(2) else None
            return float(m.group(1)), den
        return None

    def _build(self, found: list[tuple[str | None, str, Any]], mode: str, reported: float | None,
               issues: list[str]) -> ParsedJudgement:
        scores: dict[str, int] = {}
        raw_values: dict[str, object] = {}
        warnings: list[str] = []
        for key, written, value in found:
            if key is None:
                continue
            if key in scores or key in raw_values:
                warnings.append(f"duplicate:{key}")
                continue
            maximum = self.rubric.criterion(key).max_points
            denominator: float | None = None
            if isinstance(value, dict):
                denominator = next((self._number(value[k])[0] for k in ("out_of", "max") if k in value
                                    and self._number(value[k]) is not None), None)
                value = next((value[k] for k in _VALUE_KEYS if k in value), None)
            raw_values[key] = value
            number = self._number(value)
            if number is None:
                warnings.append(f"non_numeric:{key}")
                continue
            amount, den = number
            den = den if den is not None else denominator
            if den is not None and den > 0 and abs(den - maximum) > 1e-9:
                amount = amount * maximum / den
                warnings.append(f"rescaled:{key}")
            points = round_half_up(amount)
            if points < 0:
                warnings.append(f"clamped:{key}:{points}->0")
                points = 0
            elif points > maximum:
                warnings.append(f"clamped:{key}:{points}->{maximum}")
                points = maximum
            scores[key] = points
        if not scores:
            raise JudgeParseError("criteria found but none had a numeric score")
        ordered = {k: scores[k] for k in self.rubric.keys if k in scores}
        missing = tuple(k for k in self.rubric.keys if k not in scores)
        computed = sum(ordered.values())
        if reported is not None and abs(reported - computed) > 0.5:
            warnings.append(f"total_mismatch:reported={reported:g},computed={computed}")
        return ParsedJudgement(ordered, mode, tuple(warnings), missing, tuple(issues), reported, raw_values)
