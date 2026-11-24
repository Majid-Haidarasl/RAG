"""Deterministic offline comparison of new issues with the registry."""

import pytest

from rag_core.issues.domain.comparison import (
    DUPLICATE_MIN_TEXT,
    DUPLICATE_SCORE,
    RELATED_SCORE,
    ComparisonConfig,
    IssueComparator,
    IssueProfile,
    MatchLabel,
    content_tokens,
)
from rag_core.issues.domain.model import Issue, IssueCategory
from rag_core.issues.infrastructure.registry_json import issue_from_sample
from rag_core.shared_kernel.identifiers import IssueId, NodeIdentifier
from tests.fixtures.issues.seed import samples, seed_issues

pytestmark = [pytest.mark.issues, pytest.mark.issue_model]


def _profile(
    key="Q", text="", nodes=(), docs=(), category=None, contract=None
) -> IssueProfile:
    return IssueProfile(
        key, "issue", text, frozenset(nodes), frozenset(docs), category, contract
    )


def test_thresholds_are_the_documented_values() -> None:
    assert (DUPLICATE_SCORE, DUPLICATE_MIN_TEXT, RELATED_SCORE) == (0.60, 0.45, 0.25)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("كنترلر حافظه", "کنترلر حافظه"),  # Arabic kaf
        ("گزارش‌گیری", "گزارشگیری"),  # ZWNJ
        ("ایستگاه‌های انبار", "ایستگاه انبار"),  # plural suffix
        ("RAID Controllers", "raid controller"),  # case + English plural
        ("کلاینت، ویندوزی!", "کلاینت ویندوزی"),  # punctuation
    ],
)
def test_content_tokens_normalize_persian_and_english(a: str, b: str) -> None:
    assert content_tokens(a) == content_tokens(b)


def test_stopwords_and_numbers_are_dropped() -> None:
    assert content_tokens("the delay of 62 و در تأخیر") == frozenset({"delay", "تأخیر"})


@pytest.mark.parametrize("sample", samples(), ids=lambda s: s["id"])
def test_sample_expectations(sample: dict) -> None:
    result = IssueComparator().compare(issue_from_sample(sample), seed_issues())
    assert result.label.value == sample["expected_label"]
    if sample["expected_best"]:
        assert result.best.key == sample["expected_best"]


def test_persian_duplicate_matches_bilingual_record_through_its_persian_text() -> None:
    sample = samples()[0]
    best = IssueComparator().compare(issue_from_sample(sample), seed_issues()).best
    assert best.key == "AR-ISS-024"
    assert best.breakdown.text >= DUPLICATE_MIN_TEXT
    assert "AR-ISS-024" in best.shared_documents


def test_metadata_alone_never_makes_a_duplicate() -> None:
    comparator = IssueComparator()
    q = _profile(
        text="alpha beta",
        nodes={"N-SW-WIN"},
        docs={"AR-SW-019"},
        category="software",
        contract="AR-CNT-1402-118",
    )
    o = _profile(
        "O",
        text="gamma delta",
        nodes={"N-SW-WIN"},
        docs={"AR-SW-019"},
        category="software",
        contract="AR-CNT-1402-118",
    )
    b = comparator.score(q, o)
    assert b.meta == 1.0 and b.text == 0.0
    assert comparator.label(b) is MatchLabel.RELATED


def test_identical_text_and_metadata_is_a_duplicate() -> None:
    comparator = IssueComparator()
    q = _profile(text="windows client driver mismatch", nodes={"N-SW-WIN"})
    b = comparator.score(
        q, _profile("O", text="windows client driver mismatch", nodes={"N-SW-WIN"})
    )
    assert b.score == 1.0 and comparator.label(b) is MatchLabel.DUPLICATE


def test_empty_metadata_fields_are_skipped_not_counted_as_zero() -> None:
    comparator = IssueComparator()
    b = comparator.score(
        _profile(text="a1 b2", nodes={"N-SW"}),
        _profile("O", text="zz yy", nodes={"N-SW"}),
    )
    assert b.documents is None and b.contract is None and b.category is None
    assert b.meta == 1.0


def test_one_sided_contract_counts_as_mismatch() -> None:
    b = IssueComparator().score(
        _profile(text="x1", contract="AR-CNT-1402-118"), _profile("O", text="x1")
    )
    assert b.contract == 0.0


def test_unrelated_issue_is_new() -> None:
    q = Issue.create(
        IssueId("AR-ISS-070"),
        "Office chair procurement for reception",
        NodeIdentifier("N-ADM-SRV"),
        category=IssueCategory.PROCUREMENT,
    )
    result = IssueComparator().compare(q, seed_issues())
    assert result.label is MatchLabel.NEW
    assert result.by_label(MatchLabel.DUPLICATE) == []


def test_empty_registry_gives_new() -> None:
    q = issue_from_sample(samples()[0])
    result = IssueComparator().compare(q, [])
    assert result.label is MatchLabel.NEW and result.best is None


def test_ranking_is_deterministic_and_order_independent() -> None:
    q = issue_from_sample(samples()[1])
    a = IssueComparator().compare(q, seed_issues())
    b = IssueComparator().compare(q, list(reversed(seed_issues())))
    assert [(c.key, c.score) for c in a.candidates] == [
        (c.key, c.score) for c in b.candidates
    ]
    scores = [c.score for c in a.candidates]
    assert scores == sorted(scores, reverse=True)


def test_subissues_can_be_excluded() -> None:
    q = issue_from_sample(samples()[1])
    result = IssueComparator(ComparisonConfig(include_subissues=False)).compare(
        q, seed_issues()
    )
    assert all(c.kind == "issue" for c in result.candidates)
    assert result.best.key == "AR-ISS-024"


def test_query_and_its_own_subissues_are_excluded() -> None:
    issues = seed_issues()
    result = IssueComparator().compare(issues[0], issues)
    assert all(not c.key.startswith("AR-ISS-024") for c in result.candidates)


def test_closed_duplicate_is_folded_into_its_canonical_issue() -> None:
    q = Issue.create(
        IssueId("AR-ISS-071"),
        "Outbound recording is slow while one station still works",
        NodeIdentifier("N-SW-SUP"),
        affected_nodes=(NodeIdentifier("N-SW-WIN"),),
    )
    result = IssueComparator().compare(q, seed_issues())
    keys = [c.key for c in result.candidates]
    assert "AR-ISS-036" not in keys
    assert result.best.key == "AR-ISS-024" and result.best.via == "AR-ISS-036"


def test_top_k_limits_candidates() -> None:
    result = IssueComparator(ComparisonConfig(top_k=2)).compare(
        issue_from_sample(samples()[0]), seed_issues()
    )
    assert len(result.candidates) == 2


def test_minhash_prefilter_does_not_change_the_result() -> None:
    q = issue_from_sample(samples()[0])
    plain = IssueComparator().compare(q, seed_issues())
    filtered = IssueComparator(ComparisonConfig(prefilter_min_candidates=1)).compare(
        q, seed_issues()
    )
    assert (
        plain.best.key == filtered.best.key and plain.best.score == filtered.best.score
    )


class FakeEmbedder:
    """Stands in for a local embedding model; Ollama is never called in tests."""

    def __init__(self) -> None:
        self.calls = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return [
            [1.0 if "windows" in t.lower() or "ویندوز" in t else 0.0, 1.0]
            for t in texts
        ]


def test_optional_embedding_port_adds_a_semantic_component() -> None:
    fake = FakeEmbedder()
    result = IssueComparator(embedder=fake).compare(
        issue_from_sample(samples()[1]), seed_issues()
    )
    assert fake.calls == 1
    best = result.best
    assert best.breakdown.semantic is not None and 0.0 <= best.breakdown.semantic <= 1.0
    assert best.key == "AR-ISS-024/WIN"


def test_without_embedder_semantic_is_none() -> None:
    best = (
        IssueComparator().compare(issue_from_sample(samples()[1]), seed_issues()).best
    )
    assert best.breakdown.semantic is None
