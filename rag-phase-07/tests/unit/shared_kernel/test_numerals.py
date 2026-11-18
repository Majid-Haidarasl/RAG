import pytest
from decimal import Decimal

from rag_core.shared_kernel.numerals import (
    extract_numbers,
    normalize_digits,
    parse_decimal,
    strip_thousands_separators,
)

pytestmark = pytest.mark.shared_kernel


def test_normalize_digits_persian_and_arabic_indic_to_latin() -> None:
    assert normalize_digits("AR-FIN-۰۰۸") == "AR-FIN-008"
    assert normalize_digits("١٢٣") == "123"


def test_parse_decimal_western_comma() -> None:
    assert parse_decimal("2,180") == Decimal("2180")


def test_parse_decimal_arabic_thousands_separator() -> None:
    assert parse_decimal("۲٬۱۸۰") == Decimal("2180")


def test_parse_decimal_arabic_comma_as_thousands_separator() -> None:
    # Phase 2 scoring missed U+060C when used as a thousands mark.
    assert parse_decimal("2،180") == Decimal("2180")


def test_parse_decimal_persian_decimal_separator() -> None:
    assert parse_decimal("۷۸٫۸") == Decimal("78.8")


def test_parse_decimal_rejects_empty() -> None:
    with pytest.raises(ValueError):
        parse_decimal("   ")


def test_strip_thousands_leaves_decimal_point() -> None:
    assert "." in strip_thousands_separators("1,234.5")


def test_extract_numbers_from_mixed_persian_sentence() -> None:
    text = "قرارداد ۲٬۱۸۰ میلیون تومان و پیشرفت 62 درصد"
    values = [value for _, value in extract_numbers(text)]
    assert Decimal("2180") in values
    assert Decimal("62") in values
