"""Phase 13 weighted evaluation: transparent contributions, ranking, recorded scores and decision."""

from decimal import Decimal

import pytest

from rag_core.proposals.domain.evaluation import evaluate, q, text
from rag_core.proposals.infrastructure.registry_json import registry_from_dict
from tests.fixtures.rfp.samples import raw_registry, shipped_blueprint, shipped_registry

pytestmark = [pytest.mark.proposals]


def ev(raw: dict | None = None):  # noqa: ANN201
    reg = registry_from_dict(raw) if raw is not None else shipped_registry()
    return evaluate(shipped_blueprint(), reg)


def test_weighted_scores_reproduce_the_published_sheet() -> None:
    e = ev()
    a, b = e.get("PRP-A"), e.get("PRP-B")
    assert a is not None and b is not None
    assert (a.weighted, b.weighted) == (Decimal("78.8"), Decimal("75.2"))
    assert (
        a.matches_published
        and b.matches_published
        and e.published_match == e.published_total == 2
    )


def test_contributions_are_transparent() -> None:
    e = ev()
    a, b = e.get("PRP-A"), e.get("PRP-B")
    assert [(x.criterion_id, x.contribution) for x in a.lines] == [
        ("CRT-TECH", Decimal("49.2")),  # type: ignore[union-attr]
        ("CRT-FIN", Decimal("29.6")),
    ]
    assert [x.contribution for x in b.lines] == [Decimal("40.8"), Decimal("34.4")]  # type: ignore[union-attr]
    assert sum(x.contribution for x in a.lines) == a.weighted  # type: ignore[union-attr]


def test_ranking_winner_and_gaps() -> None:
    e = ev()
    assert [s.proposal_id for s in e.ranked] == ["PRP-A", "PRP-B"]
    assert e.winner.proposal_id == "PRP-A" and e.runner_up.proposal_id == "PRP-B"  # type: ignore[union-attr]
    assert e.margin == Decimal("3.6")
    assert e.cheapest.proposal_id == "PRP-B" and e.fastest.proposal_id == "PRP-B"  # type: ignore[union-attr]
    assert e.price_gap == Decimal("45") and e.duration_gap == 2
    assert e.decision_consistent


def test_the_cheaper_proposal_does_not_win_on_price() -> None:
    e = ev()
    assert e.cheapest.proposal_id != e.winner.proposal_id  # type: ignore[union-attr]


def test_price_formula_does_not_match_the_recorded_score() -> None:
    raw = raw_registry()
    raw["proposals"][0]["scores"]["CRT-FIN"] = "84.2"  # 240 / 285 x 100
    a = ev(raw).get("PRP-A")
    assert a.weighted == Decimal("82.9") and not a.matches_published  # type: ignore[union-attr]


def test_missing_section_makes_a_proposal_non_compliant() -> None:
    raw = raw_registry()
    raw["proposals"][0]["sections"].remove("test_plan")
    e = ev(raw)
    assert not e.get("PRP-A").compliant and e.get("PRP-A").missing_sections == (
        "test_plan",
    )  # type: ignore[union-attr]
    assert e.winner.proposal_id == "PRP-B" and not e.decision_consistent  # type: ignore[union-attr]


def test_missing_score_leaves_the_proposal_unranked() -> None:
    raw = raw_registry()
    del raw["proposals"][0]["scores"]["CRT-FIN"]
    a = ev(raw).get("PRP-A")
    assert a.weighted is None and a.rank == 0 and "missing score" in a.error  # type: ignore[union-attr]


def test_decision_for_the_lower_score_is_inconsistent() -> None:
    raw = raw_registry()
    raw["decision"]["selected"] = "PRP-B"
    assert not ev(raw).decision_consistent


def test_to_dict() -> None:
    data = ev().to_dict()
    assert (
        data["winner"] == "PRP-A"
        and data["margin"] == "3.6"
        and data["price_gap_mtoman"] == "45"
    )
    assert data["published_match"] == "2/2" and data["scores"][0]["lines"][0] == {  # type: ignore[index]
        "criterion": "CRT-TECH",
        "weight": "0.6",
        "score": "82",
        "contribution": "49.2",
    }


def test_number_helpers() -> None:
    assert (
        q(Decimal("49.25")) == Decimal("49.3")
        and text(Decimal("45.0")) == "45"
        and text(None) == ""
    )
