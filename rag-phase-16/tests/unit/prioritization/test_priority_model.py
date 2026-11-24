"""Phase 12 prioritization model: weights, caps, signals and scored issues."""

import pytest

from rag_core.prioritization.domain.model import (
    FACTORS,
    Caps,
    IssueSignal,
    ScoredIssue,
    Weights,
)
from rag_core.shared_kernel.errors import InvariantError
from tests.fixtures.projects.samples import WEIGHTS, signal

pytestmark = [pytest.mark.prioritization]


def test_weights_fill_missing_factors_with_zero() -> None:
    w = Weights({"risk": 0.5, "urgency": 0.5})
    assert set(w.values) == set(FACTORS) and w["priority"] == 0.0 and w["risk"] == 0.5


@pytest.mark.parametrize(
    "values",
    [
        {"risk": 0.5},
        {**WEIGHTS, "risk": 0.25},
        {**WEIGHTS, "height": 0.0},
        {"risk": 1.5, "urgency": -0.5},
    ],
)
def test_bad_weights_are_rejected(values: dict) -> None:
    with pytest.raises(InvariantError):
        Weights(values)


def test_perturbed_weights_still_sum_to_one() -> None:
    w = Weights(WEIGHTS).perturbed("risk", 1.2)
    assert sum(w.values.values()) == pytest.approx(1.0)
    assert w["risk"] == pytest.approx(0.18 / 1.03) and w["spread"] == pytest.approx(
        0.05 / 1.03
    )


def test_caps_must_be_positive() -> None:
    assert Caps().exposure_mtoman == 1000
    with pytest.raises(InvariantError):
        Caps(gaps=0)


def test_signal_invariants() -> None:
    with pytest.raises(InvariantError):
        signal(subissues=1, blocked_subissues=2)
    with pytest.raises(InvariantError):
        signal(risk=-1)
    with pytest.raises(InvariantError):
        IssueSignal(" ", "t", "t", "open")


def test_closed_and_duplicate_signals_are_not_open() -> None:
    assert signal().is_open
    assert not signal(status="closed").is_open and not signal(status="resolved").is_open
    assert not signal(status="open", duplicate_of="AR-ISS-024").is_open


def test_top_factors_order_and_positive_only() -> None:
    s = ScoredIssue(
        "AR-ISS-031",
        "t",
        "t",
        10.0,
        1,
        False,
        contributions={
            "priority": 7.5,
            "severity": 5.0,
            "urgency": 7.5,
            "risk": 7.5,
            "gaps": 0.0,
        },
    )
    assert s.top_factors() == [("priority", 7.5), ("urgency", 7.5), ("risk", 7.5)]
    assert s.top_factors(9)[-1] == ("severity", 5.0)
    assert s.to_dict()["top_factors"] == ["priority", "urgency", "risk"]
