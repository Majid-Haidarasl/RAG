"""Phase 12 scoring, ranking, legacy comparison and weight sensitivity."""

import pytest

from rag_core.prioritization.domain.scoring import PriorityScorer, factor_values, legacy_order, score, sensitivity
from rag_core.shared_kernel.errors import InvariantError
from tests.fixtures.projects.samples import caps, shipped_like_signals, signal, weights

pytestmark = [pytest.mark.prioritization]


def scorer(**kw: object) -> PriorityScorer:
    return PriorityScorer(weights(), caps(), **kw)  # type: ignore[arg-type]


def test_factor_values_are_normalized_and_capped() -> None:
    v = factor_values(signal(), caps())
    assert v["priority"] == 0.75 and v["severity"] == 0.75 and v["urgency"] == 0.8
    assert v["dependents"] == 1.0 and v["exposure"] == 1.0 and v["spread"] == 1.0
    assert v["blocked"] == 0.5 and v["gaps"] == pytest.approx(0.8)
    assert factor_values(signal(subissues=0, blocked_subissues=0), caps())["blocked"] == 0.0
    assert factor_values(signal(priority="PX", severity="odd"), caps())["priority"] == 0.5


def test_score_of_the_main_case() -> None:
    total, values, contributions = score(signal(), weights(), caps())
    assert total == pytest.approx(80.75)
    assert contributions["urgency"] == 12.0 and contributions["priority"] == 11.25 and contributions["gaps"] == 8.0
    assert sum(contributions.values()) == pytest.approx(total)
    assert values["gaps"] == 0.8


def test_more_gaps_raise_the_score() -> None:
    low = score(signal(gaps=0), weights(), caps())[0]
    high = score(signal(gaps=5), weights(), caps())[0]
    assert (low, high) == (pytest.approx(72.75), pytest.approx(82.75))
    assert score(signal(gaps=50), weights(), caps())[0] == pytest.approx(82.75)


def test_ranking_of_shipped_like_signals() -> None:
    r = scorer().rank(shipped_like_signals())
    assert r.order == ["AR-ISS-024", "AR-ISS-031", "AR-ISS-035", "AR-ISS-032", "AR-ISS-033"]
    assert [x.score for x in r.ranked] == [pytest.approx(s) for s in (80.75, 33.92, 30.17, 28.33, 17.18)]
    assert r.key_ids == ["AR-ISS-024", "AR-ISS-031", "AR-ISS-035"]
    assert r.excluded == [("AR-ISS-034", "closed"), ("AR-ISS-036", "duplicate_of:AR-ISS-024")]


def test_ranked_issue_details() -> None:
    r = scorer().rank(shipped_like_signals())
    top = r.get("AR-ISS-024")
    assert top is not None and top.rank == 1 and top.key and top.signal is not None
    assert top.top_factors() == [("urgency", 12.0), ("risk", 12.0), ("priority", 11.25)]
    assert r.get("AR-ISS-099") is None
    data = r.to_dict()
    assert data["key"] == r.key_ids and data["excluded"][1] == ["AR-ISS-036", "duplicate_of:AR-ISS-024"]


def test_key_needs_rank_and_minimum_score() -> None:
    r = scorer(key_count=2).rank(shipped_like_signals())
    assert r.key_ids == ["AR-ISS-024", "AR-ISS-031"]
    r = scorer(key_min_score=31.0).rank(shipped_like_signals())
    assert r.key_ids == ["AR-ISS-024", "AR-ISS-031"]


def test_ties_break_by_risk_urgency_then_id() -> None:
    a = signal("AR-ISS-041", risk=5, urgency=6)
    b = signal("AR-ISS-040", risk=6, urgency=5)
    c = signal("AR-ISS-039", risk=5, urgency=6)
    assert scorer().rank([a, b, c]).order == ["AR-ISS-040", "AR-ISS-039", "AR-ISS-041"]


def test_scorer_rejects_bad_settings() -> None:
    with pytest.raises(InvariantError):
        scorer(key_count=0)
    with pytest.raises(InvariantError):
        scorer(key_min_score=120)


def test_legacy_order_uses_phase_seven_formula() -> None:
    assert legacy_order(shipped_like_signals()) == ["AR-ISS-024", "AR-ISS-031", "AR-ISS-032", "AR-ISS-035",
                                                    "AR-ISS-033"]


def test_sensitivity_of_shipped_like_signals() -> None:
    s = sensitivity(scorer(), shipped_like_signals())
    assert (s.perturbations, s.top1_stable, s.key_set_stable, s.flips) == (18, 18, 18, ())
    assert s.to_dict()["flips"] == []


def test_sensitivity_reports_flips_for_close_scores() -> None:
    signals = [signal("AR-ISS-050", priority="P1", severity="low", urgency=0, risk=0, dependents=0, exposure_mtoman=0, subissues=0,
                      blocked_subissues=0, gaps=0, affected_nodes=0),
               signal("AR-ISS-051", priority="P4", severity="low", urgency=7, risk=0, dependents=0, exposure_mtoman=0, subissues=0,
                      blocked_subissues=0, gaps=0, affected_nodes=0)]
    s = sensitivity(scorer(key_count=1, key_min_score=0), signals)
    assert s.perturbations == 18 and s.key_set_stable < 18 and "priorityx0.8" in s.flips
