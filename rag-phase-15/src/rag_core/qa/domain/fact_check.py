"""Basic post-generation fact check (Phase 2 condition; Phase 10 is the judge).

Implements the shared-kernel ``FactValidator`` port. Claims extracted from
the answer (citation brackets removed first):

* identifiers — document / contract ids ``AR-XXX-NNN[-NNN]``, issue ids
  ``AR-ISS-NNN/CODE``, node ids ``N-XXX[-YYY]``, project codes ``PRJ-…``;
* numbers — Latin or Persian digits, thousands separators and decimals
  normalized (``۱٬۴۸۰`` = ``1,480`` = ``1480``). Digits glued to Latin
  letters (``P1``, ``L4``, ``qwen3``) are not numbers.

A claim is CONFIRMED when it occurs in the cited chunks, FLAGGED when it
only occurs in other retrieved (uncited) chunks, and UNSUPPORTED otherwise.
Source numbers also include simple number words (EN "four", FA "چهار"),
so "4 working hours" is confirmed by "four working hours". Person names
are out of scope here (Phase 10).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re

from rag_core.knowledge.domain.fingerprint import tokens as normalized_tokens
from rag_core.shared_kernel.fact_ports import (
    FactCheckResult,
    FactClaim,
    FactKind,
    FactValidationReport,
    FactVerdict,
)
from rag_core.shared_kernel.identifiers import DocumentId
from rag_core.shared_kernel.numerals import normalize_digits
from rag_core.shared_kernel.persian import normalize_yeh_kaf

_ID_PATTERNS: tuple[tuple[FactKind, re.Pattern[str]], ...] = (
    (FactKind.ISSUE_ID, re.compile(r"\bAR-ISS-\d{3}/[A-Z0-9]+\b")),
    (FactKind.DOCUMENT_ID, re.compile(r"\bAR-[A-Z]{2,5}-\d{2,4}(?:-\d{2,4})?\b")),
    (FactKind.DOCUMENT_ID, re.compile(r"\bPRJ-[A-Z0-9]+(?:-[A-Z0-9]+)*\b")),
    (FactKind.NODE_ID, re.compile(r"\bN-[A-Z]{2,5}(?:-[A-Z]{2,5})*\b")),
)
_NUMBER_RE = re.compile(r"(?<![A-Za-z0-9.])(\d{1,3}(?:[,٬]\d{3})+(?:[.٫]\d+)?|\d+(?:[.٫]\d+)?)(?![A-Za-z0-9])")

NUMBER_WORDS: dict[str, int] = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
    "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100,
    "یک": 1, "دو": 2, "سه": 3, "چهار": 4, "پنج": 5, "شش": 6, "هفت": 7, "هشت": 8, "نه": 9, "ده": 10,
    "یازده": 11, "دوازده": 12, "سیزده": 13, "چهارده": 14, "پانزده": 15, "شانزده": 16, "هفده": 17,
    "هجده": 18, "نوزده": 19, "بیست": 20, "سی": 30, "چهل": 40, "پنجاه": 50, "شصت": 60, "هفتاد": 70,
    "هشتاد": 80, "نود": 90, "صد": 100,
}


def _to_decimal(span: str) -> Decimal | None:
    raw = normalize_digits(span).replace(",", "").replace("٬", "").replace("٫", ".")
    try:
        return Decimal(raw).normalize()
    except InvalidOperation:
        return None


def _prepare(text: str) -> str:
    return normalize_digits(normalize_yeh_kaf(text or ""))


def extract_identifiers(text: str) -> list[FactClaim]:
    prepared = _prepare(text)
    claims: list[FactClaim] = []
    seen: set[str] = set()
    taken: list[tuple[int, int]] = []
    for kind, pattern in _ID_PATTERNS:
        for m in pattern.finditer(prepared):
            if any(a <= m.start() < b for a, b in taken):
                continue
            taken.append((m.start(), m.end()))
            value = m.group(0)
            if value not in seen:
                seen.add(value)
                claims.append(FactClaim(kind, value, value))
    return claims


def _mask_identifiers(text: str) -> str:
    out = text
    for _, pattern in _ID_PATTERNS:
        out = pattern.sub(" ", out)
    return out


def extract_numbers(text: str) -> list[FactClaim]:
    prepared = _mask_identifiers(_prepare(text))
    claims: list[FactClaim] = []
    seen: set[Decimal] = set()
    for m in _NUMBER_RE.finditer(prepared):
        value = _to_decimal(m.group(1))
        if value is None or value in seen:
            continue
        seen.add(value)
        claims.append(FactClaim(FactKind.NUMBER, m.group(1), format(value, "f")))
    return claims


def source_numbers(texts: list[str]) -> set[Decimal]:
    values: set[Decimal] = set()
    for text in texts:
        prepared = _mask_identifiers(_prepare(text))
        for m in _NUMBER_RE.finditer(prepared):
            value = _to_decimal(m.group(1))
            if value is not None:
                values.add(value)
        for tok in normalized_tokens(text):
            if tok in NUMBER_WORDS:
                values.add(Decimal(NUMBER_WORDS[tok]).normalize())
    return values


def source_identifiers(texts: list[str]) -> set[str]:
    return {c.normalized for t in texts for c in extract_identifiers(t)}


class CitedFactValidator:
    """``FactValidator`` over cited chunks, with uncited context as a hint."""

    def validate(
        self,
        generated_text: str,
        source_texts: list[str],
        *,
        source_document_ids: list[DocumentId] | None = None,
        context_texts: list[str] | None = None,
    ) -> FactValidationReport:
        from rag_core.qa.domain.citations import strip_citations

        body = strip_citations(generated_text)
        cited_ids = source_identifiers(source_texts) | {str(d) for d in (source_document_ids or [])}
        cited_nums = source_numbers(source_texts)
        ctx = context_texts or []
        ctx_ids = source_identifiers(ctx)
        ctx_nums = source_numbers(ctx)
        results: list[FactCheckResult] = []
        for claim in extract_identifiers(body):
            base_doc = claim.normalized.split("/", 1)[0]
            if claim.normalized in cited_ids or base_doc in cited_ids:
                verdict, note = FactVerdict.CONFIRMED, "in cited chunks"
            elif claim.normalized in ctx_ids or base_doc in ctx_ids:
                verdict, note = FactVerdict.FLAGGED, "only in uncited retrieved chunks"
            else:
                verdict, note = FactVerdict.UNSUPPORTED, "not in retrieved chunks"
            results.append(FactCheckResult(claim, verdict, notes=note))
        for claim in extract_numbers(body):
            value = Decimal(claim.normalized)
            if value in cited_nums:
                verdict, note = FactVerdict.CONFIRMED, "in cited chunks"
            elif value in ctx_nums:
                verdict, note = FactVerdict.FLAGGED, "only in uncited retrieved chunks"
            else:
                verdict, note = FactVerdict.UNSUPPORTED, "not in retrieved chunks"
            results.append(FactCheckResult(claim, verdict, notes=note))
        return FactValidationReport(tuple(results))


def flagged(report: FactValidationReport) -> list[FactCheckResult]:
    return [r for r in report.results if r.verdict in {FactVerdict.FLAGGED, FactVerdict.UNSUPPORTED}]
