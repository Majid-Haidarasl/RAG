"""Phase 15 hardening: Persian typography normalization edge cases (shared kernel)."""

import pytest

from rag_core.shared_kernel.persian import (
    ZWNJ,
    merge_counts,
    normalize_document_ids,
    normalize_persian_text,
    normalize_yeh_kaf,
    normalize_zwnj,
)

pytestmark = [pytest.mark.hardening, pytest.mark.shared_kernel]


def test_yeh_kaf_including_alef_maksura() -> None:
    assert normalize_yeh_kaf("علي \u0643تاب \u0649") == "علی کتاب ی"


@pytest.mark.parametrize(("text", "expected"), [
    ("می رود", f"می{ZWNJ}رود"),
    ("نمیرود", f"نمی{ZWNJ}رود"),
    (f"خانه{ZWNJ}{ZWNJ}ها", f"خانه{ZWNJ}ها"),
    ("خانه ها", f"خانه{ZWNJ}ها"),
])
def test_zwnj_rules(text: str, expected: str) -> None:
    assert normalize_zwnj(text) == expected


def test_zwnj_leaves_latin_text_alone() -> None:
    assert normalize_zwnj("plain English text") == "plain English text"


def test_document_ids_get_latin_digits_and_report_fixes() -> None:
    text, fixes = normalize_document_ids("سند AR-FIN-۰۰۸ و AR-HR-005")
    assert text == "سند AR-FIN-008 و AR-HR-005"
    assert fixes == [("AR-FIN-۰۰۸", "AR-FIN-008")]


def test_empty_text_has_zero_counts() -> None:
    assert normalize_persian_text("") == ("", {"yeh_kaf": 0, "zwnj": 0, "id_digits": 0, "arabic_indic": 0})


def test_arabic_indic_digits_become_persian_only_in_fa() -> None:
    fa_text, fa_counts = normalize_persian_text("عدد \u0663", language="fa")
    en_text, en_counts = normalize_persian_text("عدد \u0663", language="en")
    assert fa_text == "عدد ۳" and en_text == "عدد \u0663"
    assert fa_counts["arabic_indic"] == en_counts["arabic_indic"] == 1


def test_counts_for_yeh_kaf_and_ids() -> None:
    _, counts = normalize_persian_text("علي AR-HR-۰۰۵", language="fa")
    assert counts["yeh_kaf"] == 1 and counts["id_digits"] == 1


def test_merge_counts() -> None:
    assert merge_counts({"a": 1}, {"a": 2, "b": 1}) == {"a": 3, "b": 1}
    assert merge_counts() == {}
