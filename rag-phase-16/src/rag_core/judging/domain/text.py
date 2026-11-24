"""Text helpers for the judge (stdlib + shared kernel only).

``words`` follows the Phase 5 fingerprint normalization (NFKC, Persian
digits → Latin, Arabic yeh/kaf → Persian, ZWNJ removed, punctuation → space)
so a key fact counts the same way as in the Phase 8 metrics.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from rag_core.shared_kernel.numerals import normalize_digits
from rag_core.shared_kernel.persian import normalize_yeh_kaf

_INVISIBLES = {"\u200c", "\u200d", "\u200e", "\u200f", "\ufeff", "\u0640"}
BRACKET_RE = re.compile(r"\[([^\[\]]{3,200})\]")
_REF_RE = re.compile(
    r"(?P<doc>AR-[A-Z]{2,5}-\d{2,4}(?:-\d{2,4})?)"
    r"(?:\s*(?:§\s*(?P<sec>\d+)|#c(?P<cid>\d+))(?:\s*/\s*(?P<lang>fa|en))?)?",
    re.IGNORECASE,
)
_SPLIT_RE = re.compile(r"[;,،؛]")
ID_RE = re.compile(r"\b(?:AR|PRJ|N|EX)-[A-Za-z0-9][A-Za-z0-9/\-]*")
_SENTENCE_RE = re.compile(r"(?<=[.!?؟])\s+|\n+")


@dataclass(frozen=True)
class CitedRef:
    raw: str
    document_id: str
    order: int | None = None
    language: str | None = None

    @property
    def label(self) -> str:
        base = (
            self.document_id
            if self.order is None
            else f"{self.document_id} §{self.order}"
        )
        return f"{base}/{self.language}" if self.language else base


def words(text: str) -> list[str]:
    text = unicodedata.normalize("NFKC", text or "")
    text = normalize_digits(normalize_yeh_kaf(text)).lower()
    out: list[str] = []
    for ch in text:
        if ch in _INVISIBLES:
            continue
        cat = unicodedata.category(ch)
        if cat == "Mn":
            continue
        out.append(" " if cat[0] in {"P", "S"} else ch)
    return "".join(out).split()


def groups_found(text: str, groups: tuple[tuple[str, ...], ...]) -> tuple[int, int]:
    """(groups with at least one alternative in ``text``, total groups)."""
    padded = f" {' '.join(words(text))} "
    hits = sum(
        1
        for g in groups
        if any(f" {' '.join(words(alt))} " in padded for alt in g if words(alt))
    )
    return hits, len(groups)


def strip_refs(text: str) -> str:
    return BRACKET_RE.sub(" ", text or "")


def bracket_refs(text: str) -> list[CitedRef]:
    found: list[CitedRef] = []
    seen: set[str] = set()
    for bracket in BRACKET_RE.finditer(text or ""):
        inner = normalize_digits(bracket.group(1))
        for part in _SPLIT_RE.split(inner):
            m = _REF_RE.search(part.strip())
            if not m:
                continue
            sec = m.group("sec") or m.group("cid")
            ref = CitedRef(
                part.strip(),
                m.group("doc").upper(),
                int(sec) if sec else None,
                (m.group("lang") or "").lower() or None,
            )
            if ref.label not in seen:
                seen.add(ref.label)
                found.append(ref)
    return found


def has_brackets(text: str) -> bool:
    return bool(BRACKET_RE.search(text or ""))


def arabic_share(text: str) -> float | None:
    """Share of Arabic-script letters among letters, ignoring labels and identifiers."""
    body = ID_RE.sub(" ", strip_refs(text))
    arabic = latin = 0
    for ch in body:
        if "\u0600" <= ch <= "\u06ff" or "\ufb50" <= ch <= "\ufeff":
            if ch.isalpha():
                arabic += 1
        elif ch.isascii() and ch.isalpha():
            latin += 1
    total = arabic + latin
    return None if total < 10 else arabic / total


def language_matches(text: str, language: str) -> bool | None:
    share = arabic_share(text)
    if share is None:
        return None
    return share >= 0.35 if language == "fa" else share <= 0.65


def has_letters(text: str) -> bool:
    return any(ch.isalpha() for ch in text)


def sentences(text: str) -> list[str]:
    """Sentences / lines; a fragment that is only a label joins the previous one."""
    out: list[str] = []
    for part in _SENTENCE_RE.split(text or ""):
        part = part.strip()
        if not part:
            continue
        if out and not has_letters(strip_refs(part)):
            out[-1] = f"{out[-1]} {part}"
        else:
            out.append(part)
    return out


def contains_id(text: str, identifier: str) -> bool:
    return identifier.upper() in normalize_digits(text or "").upper()
