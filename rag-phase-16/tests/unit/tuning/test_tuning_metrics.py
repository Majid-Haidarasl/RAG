"""Phase 14 metrics: ranking, context facts, agreement / kappa / leniency, latency and detail level."""

import pytest

from rag_core.tuning.domain.metrics import (
    RankingRow,
    binary_agreement,
    detail_ok,
    hit_at,
    mean,
    p95,
    reciprocal_rank,
    rounded,
    sentences,
    share,
    summarize_ranking,
)

pytestmark = [pytest.mark.tuning, pytest.mark.eval_metrics]


def test_rounded_mean_and_share() -> None:
    assert rounded(None) is None and rounded(0.12345) == 0.123
    assert mean([]) is None and mean([1, 2, 4]) == 2.333
    assert share(1, 3) == 0.333 and share(0, 0) is None


def test_p95() -> None:
    assert p95([]) is None and p95([5.0]) == 5.0
    assert p95(range(1, 21)) == 19 and p95([1, 2, 3]) == 3


def test_hit_at_counts_documents_not_chunks() -> None:
    ranked = ["X", "X", "X", "Y", "Z"]
    assert hit_at(ranked, ["Z"], 3) is True and hit_at(ranked, ["Z"], 2) is False
    assert hit_at(ranked, [], 5) is None


def test_reciprocal_rank() -> None:
    assert reciprocal_rank(["A", "A", "B"], ["B"]) == 0.5
    assert reciprocal_rank(["A"], ["B"]) == 0.0 and reciprocal_rank(["A"], []) is None


def test_ranking_row() -> None:
    row = RankingRow("GQ-1", ("A", "A", "B", "C"), ("C",), (1, 2), 0.01234)
    assert row.first_rank == 3
    d = row.to_dict()
    assert d["top_docs"] == ["A", "B", "C"] and d["context_facts"] == "1/2" and d["seconds"] == 0.0123
    assert RankingRow("x", ("A",), ("B",)).first_rank is None


def test_summarize_ranking() -> None:
    rows = [RankingRow("a", ("D1",), ("D1",), (2, 2), 0.1),
            RankingRow("b", ("D2", "D1"), ("D1",), (1, 2), 0.3),
            RankingRow("c", ("D2", "D3", "D4", "D5", "D6", "D1"), ("D1",), (0, 1), 0.2)]
    s = summarize_ranking(rows)
    assert s.n == 3 and s.hit_at_1 == 0.333 and s.hit_at_3 == 0.667 and s.hit_at_5 == 0.667
    assert s.mrr == round((1 + 0.5 + 1 / 6) / 3, 3)
    assert (s.context_facts_hit, s.context_facts_total, s.full_context) == (3, 5, 1)
    assert s.context_facts == 0.6 and s.seconds_avg == 0.2 and s.misses == ["b", "c"]


def test_summary_ignores_rows_without_expected_documents() -> None:
    s = summarize_ranking([RankingRow("r", ("D1",), ())])
    assert s.n == 0 and s.hit_at_5 is None and s.context_facts is None


def test_summary_metric_lookup_and_dict() -> None:
    s = summarize_ranking([RankingRow("a", ("D1",), ("D1",), (1, 1))])
    assert s.metric("hit_at_5") == 1.0 and s.metric("context_facts") == 1.0 and s.metric("nope") is None
    d = s.to_dict()
    assert d["context_facts_count"] == "1/1" and d["rows"][0]["id"] == "a"


def test_binary_agreement_perfect() -> None:
    a = binary_agreement([(True, True), (False, False), (True, True), (False, False)])
    assert (a.n, a.agree, a.accuracy, a.kappa, a.leniency) == (4, 4, 1.0, 1.0, 0.0)


def test_binary_agreement_lenient_judge() -> None:
    a = binary_agreement([(True, True), (True, False), (True, False), (False, False)])
    assert (a.true_accepts, a.false_accepts, a.true_rejects, a.false_rejects) == (1, 2, 1, 0)
    assert a.accuracy == 0.5 and a.leniency == 0.667 and a.kappa == 0.2


def test_kappa_undefined_when_one_class_only() -> None:
    a = binary_agreement([(True, True), (True, True)])
    assert a.kappa is None and a.accuracy == 1.0 and a.leniency is None


def test_empty_agreement() -> None:
    a = binary_agreement([])
    assert a.n == 0 and a.accuracy is None and a.to_dict()["leniency"] is None


def test_sentences() -> None:
    assert sentences("One. Two? سه؟ Four!") == ["One.", "Two?", "سه؟", "Four!"]
    assert sentences("a\n\nb") == ["a", "b"] and sentences("") == []


def test_detail_levels() -> None:
    four = "A. B. C. D."
    assert detail_ok("A.", "short") and not detail_ok(four, "short") and detail_ok(four, "list")
    assert not detail_ok("A. B. C.", "refusal") and detail_ok("A. B.", "refusal")
    assert not detail_ok("", "short") and detail_ok(four, "unknown")
