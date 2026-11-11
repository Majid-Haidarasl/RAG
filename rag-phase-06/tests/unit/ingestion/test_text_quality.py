"""Garbled / fragmented text detector (Phase 5.1 PDF fix)."""

import pytest

from rag_core.ingestion.domain.text_quality import assess_text_quality

pytestmark = pytest.mark.ingestion

CLEAN_FA = (
    "این سیاست تصمیم مرخصی و حضور را قابل ردیابی می‌کند و همزمان تداوم خدمت و حریم خصوصی کارکنان را حفظ می‌کند. "
    "مدیر مستقیم پوشش کار را برنامه‌ریزی می‌کند و حسابداری نتیجه مجاز حضور را برای حقوق استفاده می‌کند. "
    "درخواست مرخصی باید پیش از شروع در سامانه ثبت شود و تأیید مدیر با تاریخ و ساعت نگهداری شود. "
) * 2


def test_clean_persian_is_ok() -> None:
    q = assess_text_quality(CLEAN_FA)
    assert q.verdict == "ok" and not q.is_garbled
    assert q.metrics["fragment_ratio"] < 0.03


def test_clean_english_is_ok() -> None:
    assert assess_text_quality("Annual leave is 26 days and must be approved in advance. " * 5).verdict == "ok"


def test_empty_text_is_empty_not_garbled() -> None:
    assert assess_text_quality("  \n").verdict == "empty"


def test_cid_placeholders_are_garbled() -> None:
    text = " ".join(["(cid:11)ش", "هرود", "(cid:22)ئ", "AR-FIN-008"] * 20)
    q = assess_text_quality(text)
    assert q.is_garbled and any("cid" in r for r in q.reasons)


def test_presentation_forms_are_garbled() -> None:
    text = "\ufeb3\ufef4\ufe8e\ufeb3\ufe98 \ufee3\ufeae\ufea7\ufebc\ufef0 " * 20
    q = assess_text_quality(text)
    assert q.is_garbled and any("presentation" in r for r in q.reasons)


def test_replacement_characters_are_garbled() -> None:
    assert assess_text_quality("abc \ufffd\ufffd def " * 10).is_garbled


def test_reversed_visual_order_persian_is_garbled() -> None:
    reversed_text = " ".join(w[::-1] for w in CLEAN_FA.split())
    q = assess_text_quality(reversed_text)
    assert q.is_garbled
    assert any("reversed" in r for r in q.reasons)


def test_split_words_are_fragmented_but_usable() -> None:
    fragmented = CLEAN_FA.replace("مرخصی", "مرخ صی").replace("حضور", "حض ور").replace("خدمت", "خ دمت")
    fragmented = fragmented.replace("کارکنان", "کارکن ان").replace("مستقیم", "مست قیم").replace("نتیجه", "نت یجه")
    q = assess_text_quality(fragmented)
    assert q.verdict == "fragmented" and not q.is_garbled
    assert q.metrics["fragment_ratio"] > 0.03


def test_common_short_words_are_not_fragments() -> None:
    text = "از به در با که را تا یا هر آن و " * 10 + CLEAN_FA
    assert assess_text_quality(text).verdict == "ok"
