import pytest

from rag_core.knowledge.domain.fingerprint import (
    MinHasher,
    containment,
    guess_language,
    jaccard,
    lsh_buckets,
    normalize_for_hash,
    normalized_hash,
    shingles,
)

pytestmark = [pytest.mark.knowledge, pytest.mark.dedup]


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("می‌رود", "می رود"),
        ("كتاب علي", "کتاب علی"),
        ("مبلغ ۱۲۰۰ ریال", "مبلغ 1200 ریال"),
        ("Hello,  World!", "hello world"),
        ("كتـــاب", "کتاب"),
        ("مُدیر", "مدیر"),
    ],
)
def test_normalized_hash_ignores_rendering_differences(a: str, b: str) -> None:
    assert normalized_hash(a) == normalized_hash(b)


def test_normalized_hash_distinguishes_real_changes() -> None:
    assert normalized_hash("مبلغ ۱۲۰۰ ریال") != normalized_hash("مبلغ ۱۳۰۰ ریال")


def test_normalize_for_hash_removes_whitespace_and_punctuation() -> None:
    assert normalize_for_hash("a, b.\n c") == "abc"


def test_shingles_and_set_metrics() -> None:
    s = shingles("a b c d")
    assert s == {"a b c", "b c d"}
    assert shingles("a b") == {"a b"}
    assert jaccard({"x", "y"}, {"y", "z"}) == pytest.approx(1 / 3)
    assert containment({"x"}, {"x", "y"}) == 1.0
    assert containment(set(), {"x"}) == 0.0


def test_minhash_is_deterministic_and_estimates_jaccard() -> None:
    a = shingles(" ".join(f"w{i}" for i in range(200)))
    b = shingles(" ".join(f"w{i}" for i in range(20, 220)))
    h1, h2 = MinHasher(128, seed=7), MinHasher(128, seed=7)
    assert h1.signature(a) == h2.signature(a)
    est = MinHasher.estimate(h1.signature(a), h1.signature(b))
    assert abs(est - jaccard(a, b)) < 0.12


def test_lsh_bands_require_divisible_signature() -> None:
    assert len(lsh_buckets(tuple(range(64)), 16)) == 16
    with pytest.raises(ValueError):
        lsh_buckets(tuple(range(64)), 7)


def test_guess_language_by_script() -> None:
    assert guess_language("این یک متن فارسی برای آزمون زبان است") == "fa"
    assert guess_language("This is an English sentence for testing") == "en"
    assert guess_language("123 456") is None
