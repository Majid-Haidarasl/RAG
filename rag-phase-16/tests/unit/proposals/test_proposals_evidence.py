"""Phase 13 proposal grounding: registered numbers and statements must be in the evidence."""

import pytest

from rag_core.proposals.domain.evidence import ground_registry, registered_numbers
from rag_core.proposals.infrastructure.registry_json import registry_from_dict
from rag_core.qa.domain.fact_check import CitedFactValidator, source_numbers
from tests.fixtures.rfp.samples import raw_registry, registry_texts, shipped_registry

pytestmark = [pytest.mark.proposals]

V = CitedFactValidator()
TEXTS = registry_texts(shipped_registry())


def ground(raw: dict, languages=("fa", "en")):
    return ground_registry(registry_from_dict(raw), TEXTS, V, source_numbers, languages)


def test_registered_numbers_of_a_proposal() -> None:
    a = shipped_registry().get("PRP-A")
    assert [n for n, _ in registered_numbers(a)] == [
        "price",
        "duration",
        "score:CRT-TECH",
        "score:CRT-FIN",  # type: ignore[arg-type]
        "published",
    ]


def test_shipped_registry_grounds_in_both_languages() -> None:
    ev = ground(raw_registry())
    assert ev.ok
    for lang in ("fa", "en"):
        assert ev.grounded("numbers", lang) == ev.total("numbers", lang) == 2
        assert (
            ev.grounded("statements", lang) == ev.total("statements", lang) == 4
        )  # A clar., B fb + clar., decision


def test_wrong_price_is_missing() -> None:
    raw = raw_registry()
    raw["proposals"][1]["price_mtoman"] = 250
    bad = ground(raw, ("en",)).failures()
    assert [(f.ref, f.missing) for f in bad] == [("PRP-B", ("price=250",))]


def test_price_formula_score_is_missing() -> None:
    raw = raw_registry()
    raw["proposals"][0]["scores"]["CRT-FIN"] = "84.2"
    assert [f.missing for f in ground(raw, ("fa",)).failures()] == [
        ("score:CRT-FIN=84.2",)
    ]


def test_invented_number_in_feedback() -> None:
    raw = raw_registry()
    raw["proposals"][1]["feedback_en"] += " Its score was 91."
    bad = ground(raw, ("en",)).failures()
    assert [(f.ref, f.missing) for f in bad] == [("PRP-B/feedback", ("91",))]


def test_no_evidence_text() -> None:
    ev = ground_registry(shipped_registry(), {}, V, source_numbers)
    assert not ev.ok and {f.missing for f in ev.numbers} == {("no evidence text",)}
