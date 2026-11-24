"""Phase 15 hardening: digit normalization, separators and number parsing (shared kernel)."""

from decimal import Decimal

import pytest

from rag_core.shared_kernel.numerals import (
    extract_numbers,
    normalize_digits,
    parse_decimal,
    strip_thousands_separators,
)

pytestmark = [pytest.mark.hardening, pytest.mark.shared_kernel]


def test_normalize_digits_maps_persian_and_arabic_indic() -> None:
    assert normalize_digits("۱۲۳\u0664\u0665") == "12345"


def test_normalize_digits_empty_and_other_characters() -> None:
    assert normalize_digits("") == ""
    assert normalize_digits("AR-FIN-۰۰۸ و x") == "AR-FIN-008 و x"


@pytest.mark.parametrize("text", ["2,180", "2\u060c180", "2\u00a0180"])
def test_strip_thousands_separators(text: str) -> None:
    assert strip_thousands_separators(text) == "2180"


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("2 180", Decimal("2180")),
        ("1,234.5", Decimal("1234.5")),
        ("\u0667\u0668\u066b\u0668", Decimal("78.8")),
        ("-5", Decimal("-5")),
    ],
)
def test_parse_decimal_accepts(text: str, value: Decimal) -> None:
    assert parse_decimal(text) == value


@pytest.mark.parametrize("text", ["NaN", "Infinity", "1e5", "1.2.3"])
def test_parse_decimal_rejects(text: str) -> None:
    with pytest.raises(ValueError):
        parse_decimal(text)


def test_extract_numbers_keeps_spans_and_values() -> None:
    found = extract_numbers("امتیاز ۷۸٫۸ و 62 درصد")
    assert [span for span, _ in found] == ["۷۸٫۸", "62"]
    assert [value for _, value in found] == [Decimal("78.8"), Decimal("62")]


def test_extract_numbers_without_digits() -> None:
    assert extract_numbers("no numbers here / بدون عدد") == []
