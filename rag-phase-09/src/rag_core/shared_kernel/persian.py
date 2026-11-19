"""Persian text normalization used at ingestion and later by the fact validator."""

from __future__ import annotations

import re

from rag_core.shared_kernel.numerals import normalize_digits

ARABIC_YEH = "\u064a"
ALEF_MAKSURA = "\u0649"
PERSIAN_YEH = "\u06cc"
ARABIC_KAF = "\u0643"
PERSIAN_KAF = "\u06a9"
ZWNJ = "\u200c"

# Document / contract / RFP / issue identifiers that must store Latin digits (finding D1).
_ID_RE = re.compile(
    r"AR-[A-Z]{2,5}-[0-9\u06F0-\u06F9\u0660-\u0669]{2,4}"
    r"(?:-[0-9\u06F0-\u06F9\u0660-\u0669]{2,4})?"
    r"(?:/[A-Z0-9]+)?"
)

# "می " or "نمی " before a verb, or a missing half-space: میرود → می‌رود
_MI_SPACE = re.compile(r"(?<![\w\u200c])(ن?می)[\u00a0\u2009 ]+(?=\S)")
_MI_GLUED = re.compile(r"(?<![\w\u200c])(ن?می)(?=[اآأإءبپتثجچحخدذرزژسشصضطظعغفقکكگلمنوهیيى])")

# Plural/suffix " ها " after a Persian letter: خانه‌ ها / خانه ها → خانه‌ها
_HA_SPACE = re.compile(
    r"([\u0600-\u06FF])[ ]+ها(?=[\s\.,،؛:!?؟]|$)"
)

# Arabic-Indic digits → Persian digits (prose). Latin digits are left alone.
_ARABIC_INDIC_TO_PERSIAN = str.maketrans("٠١٢٣٤٥٦٧٨٩", "۰۱۲۳۴۵۶۷۸۹")


def normalize_yeh_kaf(text: str) -> str:
    return (
        text.replace(ARABIC_YEH, PERSIAN_YEH)
        .replace(ALEF_MAKSURA, PERSIAN_YEH)
        .replace(ARABIC_KAF, PERSIAN_KAF)
    )


def normalize_zwnj(text: str) -> str:
    """Collapse duplicate ZWNJs and insert obvious missing half-spaces."""
    text = text.replace(ZWNJ + ZWNJ, ZWNJ)
    text = _MI_SPACE.sub(rf"\1{ZWNJ}", text)
    text = _MI_GLUED.sub(rf"\1{ZWNJ}", text)
    text = _HA_SPACE.sub(rf"\1{ZWNJ}ها", text)
    text = text.replace(ZWNJ + ZWNJ, ZWNJ)
    return text


def normalize_document_ids(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Rewrite identifier digits to Latin. Returns (text, list of (original, fixed))."""
    fixes: list[tuple[str, str]] = []

    def _repl(match: re.Match[str]) -> str:
        original = match.group(0)
        fixed = normalize_digits(original)
        if fixed != original:
            fixes.append((original, fixed))
        return fixed

    return _ID_RE.sub(_repl, text), fixes


def normalize_persian_text(text: str, *, language: str | None = None) -> tuple[str, dict[str, int]]:
    """Normalize typography. Counts are for the ingestion summary.

    Latin digits in prose are preserved. Arabic-Indic digits in Persian
    documents become Persian digits. Identifiers always receive Latin digits.
    """
    if not text:
        return text, {"yeh_kaf": 0, "zwnj": 0, "id_digits": 0, "arabic_indic": 0}

    yeh_kaf = text.count(ARABIC_YEH) + text.count(ALEF_MAKSURA) + text.count(ARABIC_KAF)
    text = normalize_yeh_kaf(text)

    arabic_indic = sum(text.count(ch) for ch in "٠١٢٣٤٥٦٧٨٩")
    if language == "fa" and arabic_indic:
        text = text.translate(_ARABIC_INDIC_TO_PERSIAN)

    before_zwnj = text
    text = normalize_zwnj(text)
    zwnj = 0 if text == before_zwnj else 1

    text, id_fixes = normalize_document_ids(text)
    return text, {
        "yeh_kaf": yeh_kaf,
        "zwnj": zwnj,
        "id_digits": len(id_fixes),
        "arabic_indic": arabic_indic,
    }


def merge_counts(*counts: dict[str, int]) -> dict[str, int]:
    total: dict[str, int] = {}
    for item in counts:
        for key, value in item.items():
            total[key] = total.get(key, 0) + value
    return total
