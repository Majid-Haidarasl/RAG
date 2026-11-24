"""Phase 10 metrics: acceptance, gold agreement, negative rejection and judge agreement (kappa)."""

import pytest

from rag_core.judging.domain.metrics import (
    acceptance,
    agreement,
    gold_metrics,
    rejection_rate,
)
from rag_core.judging.domain.results import JudgeResult
from rag_core.judging.domain.rubric import default_rubric
from rag_core.judging.domain.threshold import AcceptancePolicy
from tests.fixtures.judge.samples import FULL, qa_en

pytestmark = [pytest.mark.judging, pytest.mark.judge]

POLICY = AcceptancePolicy(default_rubric())
LOW = dict(FULL, grounding=1)


def _result(
    case_id: str,
    scores: dict | None,
    *,
    gold: str = "",
    origin: str = "test",
    tags: tuple = (),
    judge: str = "rule",
) -> JudgeResult:
    case = qa_en(case_id=case_id, gold=gold, origin=origin, tags=tags)
    outcome = POLICY.error("x") if scores is None else POLICY.decide(scores)
    return JudgeResult.for_case(case, judge, scores or {}, outcome)


def test_acceptance() -> None:
    rows = [_result("A", FULL), _result("B", LOW), _result("C", None)]
    a = acceptance(rows)
    assert (a["n"], a["accepted"], a["rejected"], a["errors"]) == (3, 1, 1, 1)
    assert a["rate"] == 0.333 and a["mean_total"] == 18.0 and a["min_total"] == 16
    assert a["criterion_means"]["grounding"] == 3.0
    assert a["rejected_cases"] == ["B(16)", "C(0)"]
    assert acceptance([])["rate"] is None


def test_gold_metrics_with_excluded_tags() -> None:
    rows = [
        _result("P", FULL, gold="accept"),
        _result("N", LOW, gold="reject"),
        _result("B", FULL, gold="reject", tags=("rule_blind_spot",)),
        _result("U", FULL),
    ]
    g = gold_metrics(rows)
    assert (g["n"], g["agree"], g["positives_accepted"], g["negatives_rejected"]) == (
        3,
        2,
        1,
        1,
    )
    assert g["disagreements"] == ["B:accept(20)"]
    g2 = gold_metrics(rows, exclude_tags=("rule_blind_spot",))
    assert g2["n"] == 2 and g2["accuracy"] == 1.0


def test_rejection_rate_by_kind() -> None:
    rows = [
        _result("A~wrong_number", LOW, origin="negative:wrong_number"),
        _result("B~off_topic", FULL, origin="negative:off_topic"),
    ]
    r = rejection_rate(rows)
    assert r["rejected"] == 1 and r["rate"] == 0.5
    assert r["by_kind"] == {
        "wrong_number": {"rejected": 1, "n": 1},
        "off_topic": {"rejected": 0, "n": 1},
    }
    assert r["accepted_cases"] == ["B~off_topic(20)"]


def test_agreement_and_kappa() -> None:
    first = [
        _result("A", FULL),
        _result("B", LOW),
        _result("C", FULL),
        _result("D", LOW),
    ]
    same = [_result(r.case_id, FULL if r.accepted else LOW, judge="llm") for r in first]
    assert agreement(first, same) == {
        "n": 4,
        "agree": 4,
        "rate": 1.0,
        "kappa": 1.0,
        "disagreements": [],
    }
    flipped = [
        _result(r.case_id, LOW if r.accepted else FULL, judge="llm") for r in first
    ]
    res = agreement(first, flipped)
    assert res["agree"] == 0 and res["kappa"] == -1.0 and len(res["disagreements"]) == 4
    all_accept = [_result(r.case_id, FULL, judge="llm") for r in first[:1]]
    assert (
        agreement(first[:1], all_accept)["kappa"] is None
    )  # no variation: kappa undefined
    assert agreement([], first)["n"] == 0
