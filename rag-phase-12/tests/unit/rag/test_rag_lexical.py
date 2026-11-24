"""BM25 over Persian-normalized tokens."""

import math

import pytest

from rag_core.rag.domain.lexical import Bm25Index, lexical_tokens

pytestmark = [pytest.mark.rag, pytest.mark.retrieval]


def test_tokens_normalize_persian_variants() -> None:
    # Arabic yeh/kaf, ZWNJ, Persian digits all fold onto one form.
    assert lexical_tokens("مرخصي ساعتي ۱۶ ساعت") == lexical_tokens(
        "مرخصی ساعتی 16 ساعت"
    )
    assert lexical_tokens("پیش‌پرداخت") == lexical_tokens("پیشپرداخت") == ["پیشپرداخت"]


def test_stopwords_removed() -> None:
    assert lexical_tokens("the response of the team") == ["response", "team"]
    assert "در" not in lexical_tokens("در روز و در ماه")


def test_light_plural_stripping() -> None:
    assert lexical_tokens("policies")[0] == "policy"
    assert lexical_tokens("hours") == ["hour"]
    assert lexical_tokens("قراردادها") == ["قرارداد"]


def test_digits_kept_single_letters_dropped() -> None:
    assert lexical_tokens("P 1 x") == ["1"]


def test_ranking_prefers_matching_document() -> None:
    idx = Bm25Index(
        [
            ("a", "مرخصی ساعتی ۴ ساعت در روز"),
            ("b", "پاسخ اولویت ۱ ظرف ۳۰ دقیقه"),
            ("c", "گزارش مالی فصلی"),
        ]
    )
    hits = idx.search("سقف مرخصی ساعتی", 3)
    assert hits[0][0] == "a"
    assert all(score > 0 for _, score in hits)


def test_persian_query_with_arabic_letters_matches() -> None:
    idx = Bm25Index([("a", "مرخصی ساعتی"), ("b", "قرارداد")])
    assert idx.search("مرخصي", 1)[0][0] == "a"


def test_allowed_subset_restricts_results() -> None:
    idx = Bm25Index([("a", "leave hours"), ("b", "leave policy")])
    assert [k for k, _ in idx.search("leave", 5, allowed=["b"])] == ["b"]
    assert idx.search("leave", 5, allowed=["zzz"]) == []


def test_no_match_or_stopword_query_returns_empty() -> None:
    idx = Bm25Index([("a", "leave hours")])
    assert idx.search("the of and", 5) == []
    assert idx.search("blockchain", 5) == []
    assert Bm25Index().search("leave", 5) == []


def test_idf_is_positive_and_rarer_terms_weigh_more() -> None:
    idx = Bm25Index([("a", "leave common"), ("b", "common"), ("c", "common")])
    assert idx.idf("leave") > idx.idf("common") > 0
    assert math.isclose(idx.idf("unknown"), math.log(1 + (3 + 0.5) / 0.5))


def test_add_replace_and_remove() -> None:
    idx = Bm25Index([("a", "leave")])
    idx.add("a", "repair")
    assert idx.search("leave", 5) == [] and idx.search("repair", 5)[0][0] == "a"
    idx.remove("a")
    assert len(idx) == 0 and "a" not in idx
    idx.remove("missing")  # no error


def test_length_normalization_favours_focused_chunk() -> None:
    idx = Bm25Index([("short", "leave hours"), ("long", "leave " + "filler " * 60)])
    assert idx.search("leave", 2)[0][0] == "short"


def test_deterministic_tie_break_by_key() -> None:
    idx = Bm25Index([("b", "leave"), ("a", "leave")])
    assert [k for k, _ in idx.search("leave", 2)] == ["a", "b"]
