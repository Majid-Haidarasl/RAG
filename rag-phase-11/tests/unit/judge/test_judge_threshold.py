"""Phase 10 acceptance policy: total >= 18/20 and every criterion at its minimum."""

import pytest

from rag_core.judging.domain.rubric import default_rubric
from rag_core.judging.domain.threshold import AcceptancePolicy, Decision
from rag_core.shared_kernel.errors import InvariantError
from tests.fixtures.judge.samples import FULL

pytestmark = [pytest.mark.judging, pytest.mark.judge]


def _policy() -> AcceptancePolicy:
    return AcceptancePolicy(default_rubric())


def test_full_marks_accept() -> None:
    outcome = _policy().decide(FULL)
    assert outcome.decision is Decision.ACCEPT and outcome.accepted
    assert outcome.total == 20 and outcome.out_of == 20 and outcome.reasons == ()


def test_exactly_eighteen_with_minimums_accepts() -> None:
    scores = {"grounding": 4, "correctness": 4, "citation": 4, "completeness": 3, "clarity": 3}
    outcome = _policy().decide(scores)
    assert outcome.total == 18 and outcome.accepted


def test_seventeen_rejects_on_total() -> None:
    scores = {"grounding": 4, "correctness": 4, "citation": 3, "completeness": 3, "clarity": 3}
    outcome = _policy().decide(scores)
    assert outcome.total == 17 and outcome.decision is Decision.REJECT
    assert outcome.reasons == ("total 17<18",)


def test_high_total_with_weak_grounding_rejects() -> None:
    scores = {"grounding": 3, "correctness": 5, "citation": 4, "completeness": 3, "clarity": 3}
    outcome = _policy().decide(scores)
    assert outcome.total == 18 and not outcome.accepted
    assert outcome.reasons == ("grounding 3<4",)


@pytest.mark.parametrize(("key", "low"), [("grounding", 3), ("correctness", 3), ("citation", 2),
                                          ("completeness", 1), ("clarity", 1)])
def test_every_minimum_is_enforced(key: str, low: int) -> None:
    scores = dict(FULL)
    scores[key] = low
    outcome = _policy().decide(scores)
    assert not outcome.accepted
    assert f"{key} {low}<{default_rubric().minimums[key]}" in outcome.reasons


def test_missing_criterion_counts_as_zero_and_rejects() -> None:
    scores = {k: v for k, v in FULL.items() if k != "clarity"}
    outcome = _policy().decide(scores)
    assert outcome.total == 17 and not outcome.accepted
    assert "missing:clarity" in outcome.reasons


def test_hard_failures_reject_full_marks() -> None:
    outcome = _policy().decide(FULL, hard_failures=["fabricated_citation"])
    assert outcome.total == 20 and outcome.reasons == ("hard:fabricated_citation",)
    assert outcome.decision is Decision.REJECT


@pytest.mark.parametrize("scores", [{"grounding": 6}, {"grounding": -1}, {"style": 1}, {"grounding": True},
                                    {"grounding": 4.5}])
def test_invalid_scores_raise(scores: dict) -> None:
    with pytest.raises(InvariantError):
        _policy().decide(scores)


def test_error_outcome_is_never_an_acceptance() -> None:
    outcome = _policy().error("unparseable")
    assert outcome.decision is Decision.ERROR and not outcome.accepted
    assert outcome.total == 0 and outcome.reasons == ("error:unparseable",)
    assert outcome.to_dict() == {"decision": "error", "total": 0, "out_of": 20, "reasons": ["error:unparseable"]}
