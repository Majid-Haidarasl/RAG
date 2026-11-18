"""Digit and number normalization used by identifiers and the fact validator.

Persian typography mixes Western digits, Persian digits (U+06F0–U+06F9),
Arabic-Indic digits (U+0660–U+0669), and several thousands separators.
Phase 2 scoring missed the Arabic comma as a thousands separator; this
module treats all of the separators below as grouping marks when they
appear between digits.

Implementation of full claim-vs-source verification is deferred to Phase 8.
These primitives are stable and are already needed by value objects.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re

PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
ARABIC_INDIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
LATIN_DIGITS = "0123456789"

# U+066C Arabic thousands separator, U+060C Arabic comma (often misused
# as a thousands mark in Persian documents), Western comma, underscore,
# regular/narrow/no-break spaces.
THOUSANDS_SEPARATORS = frozenset(
    {
        ",",
        "٬",  # ٬
        "،",  # ،
        "_",
        " ",
        " ",
        " ",
        " ",
    }
)

# Western decimal point and U+066B Arabic decimal separator.
DECIMAL_SEPARATORS = frozenset({".", "٫"})

_DIGIT_TABLE = str.maketrans(PERSIAN_DIGITS + ARABIC_INDIC_DIGITS, LATIN_DIGITS * 2)

# Digit in any of the three scripts.
_DIGIT = r"[0-9۰-۹٠-٩]"


def normalize_digits(text: str) -> str:
    """Map Persian and Arabic-Indic digits to Latin digits. Leave other characters."""
    if not text:
        return text
    return text.translate(_DIGIT_TABLE)


def strip_thousands_separators(text: str) -> str:
    """Remove recognized thousands separators. Digits are not rewritten."""
    return "".join(ch for ch in text if ch not in THOUSANDS_SEPARATORS)


def parse_decimal(text: str) -> Decimal:
    """Parse a number that may use mixed digits and Persian/Arabic separators.

    Examples accepted: ``2,180``, ``۲٬۱۸۰``, ``2،180``, ``2180``, ``78.8``, ``۷۸٫۸``.
    """
    raw = normalize_digits(text.strip())
    if not raw:
        raise ValueError("empty number")
    chars: list[str] = []
    decimal_seen = False
    for ch in raw:
        if ch in THOUSANDS_SEPARATORS:
            continue
        if ch in DECIMAL_SEPARATORS:
            if decimal_seen:
                raise ValueError(f"multiple decimal separators in {text!r}")
            chars.append(".")
            decimal_seen = True
            continue
        chars.append(ch)
    normalized = "".join(chars)
    try:
        return Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError(f"not a number: {text!r}") from exc


def extract_numbers(text: str) -> list[tuple[str, Decimal]]:
    """Return (original_span, parsed_value) for numeric tokens in text."""
    # Number with optional grouping and optional decimal part.
    seps = r"[\s,٬،_]*"
    dec = r"[\.٫]"
    pattern = re.compile(
        rf"{_DIGIT}+(?:{seps}{_DIGIT}+)*(?:{dec}{_DIGIT}+)?"
    )
    found: list[tuple[str, Decimal]] = []
    for match in pattern.finditer(text):
        span = match.group(0)
        found.append((span, parse_decimal(span)))
    return found
