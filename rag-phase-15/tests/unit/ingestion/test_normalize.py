import pytest

from rag_core.shared_kernel.persian import (
    normalize_document_ids,
    normalize_persian_text,
    normalize_yeh_kaf,
    normalize_zwnj,
)

pytestmark = pytest.mark.ingestion


def test_arabic_yeh_and_kaf_become_persian() -> None:
    assert normalize_yeh_kaf("يك نسخه") == "یک نسخه"
    assert "ي" not in normalize_yeh_kaf("آزمايشي")


def test_zwnj_inserted_for_mi_prefix() -> None:
    assert "\u200c" in normalize_zwnj("میرود")
    assert normalize_zwnj("می رود") == "می‌رود"
    assert "خانه\u200cها" == normalize_zwnj("خانه ها")


def test_persian_digits_in_document_id_become_latin() -> None:
    text, fixes = normalize_document_ids("see AR-FIN-۰۰۸ and AR-HW-۰۱۲")
    assert "AR-FIN-008" in text
    assert "AR-HW-012" in text
    assert ("AR-FIN-۰۰۸", "AR-FIN-008") in fixes
    assert len(fixes) == 2


def test_latin_digits_in_prose_are_kept_when_normalizing_persian() -> None:
    text, counts = normalize_persian_text("مرخصی 26 روز و شناسه AR-HR-۰۰۵", language="fa")
    assert "26" in text
    assert "AR-HR-005" in text
    assert counts["id_digits"] == 1
