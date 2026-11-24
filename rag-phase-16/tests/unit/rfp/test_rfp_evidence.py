"""Phase 13 blueprint grounding: statements, link roles and weights must be in the cited documents."""

from decimal import Decimal

import pytest

from rag_core.qa.domain.fact_check import CitedFactValidator, source_numbers
from rag_core.rfp.domain.evidence import ground_blueprint, ground_statement
from tests.fixtures.rfp.samples import (
    blueprint_texts,
    shipped_blueprint,
    with_criterion,
    with_link,
    with_requirement,
)

pytestmark = [pytest.mark.rfp_gen]

V = CitedFactValidator()


def test_shipped_blueprint_grounds_in_both_languages() -> None:
    bp = shipped_blueprint()
    ev = ground_blueprint(bp, blueprint_texts(bp), V, source_numbers)
    assert ev.ok and ev.failures() == []
    for lang in ("fa", "en"):
        assert ev.grounded(lang) == ev.total(lang) == 18  # 11 requirements + 7 links
    assert sum(1 for w in ev.weights if w.grounded) == 4  # 2 criteria x 2 languages


def test_invented_number_in_a_requirement() -> None:
    bp = shipped_blueprint()
    texts = blueprint_texts(bp)
    statement = bp.requirement("REQ-EVALUATION").statement_en.replace("60%", "65%")  # type: ignore[union-attr]
    ev = ground_blueprint(
        with_requirement(bp, "REQ-EVALUATION", statement_en=statement),
        texts,
        V,
        source_numbers,
    )
    bad = ev.failures()
    assert [(f.ref, f.language) for f in bad] == [
        ("BP-WEB-REPORTING/REQ-EVALUATION", "en")
    ]
    assert bad[0].missing == ("65",)


def test_invented_id_in_a_link_role() -> None:
    bp = shipped_blueprint()
    texts = blueprint_texts(bp)
    ev = ground_blueprint(
        with_link(bp, "LNK-COST", role_en="controls the cost under AR-FIN-099"),
        texts,
        V,
        source_numbers,
    )
    assert [(f.ref, f.missing) for f in ev.failures()] == [
        ("BP-WEB-REPORTING/LNK-COST", ("AR-FIN-099",))
    ]


def test_weight_not_in_the_text() -> None:
    bp = shipped_blueprint()
    texts = blueprint_texts(bp)
    ev = ground_blueprint(
        with_criterion(bp, "CRT-FIN", weight=Decimal("0.5")),
        texts,
        V,
        source_numbers,
        languages=("en",),
    )
    assert [(w.ref, w.missing) for w in ev.weights if not w.grounded] == [
        ("BP-WEB-REPORTING/CRT-FIN", ("weight=50%",))
    ]


def test_no_evidence_text() -> None:
    ev = ground_blueprint(shipped_blueprint(), {}, V, source_numbers)
    assert not ev.ok
    assert {f.missing for f in ev.failures()} == {("no evidence text",)}


def test_empty_statement() -> None:
    r = ground_statement(
        "X", "  ", ("AR-RFP-025",), "en", {("AR-RFP-025", "en"): ["text"]}, V
    )
    assert not r.grounded and r.missing == ("no statement",)


def test_persian_digits_in_the_source_ground_latin_digits() -> None:
    texts = {("AR-RFP-025", "fa"): ["وزن فنی ۶۰ درصد است."]}
    assert ground_statement(
        "X", "وزن فنی 60 درصد است.", ("AR-RFP-025",), "fa", texts, V
    ).grounded


def test_one_language_only_and_to_dict() -> None:
    bp = shipped_blueprint()
    ev = ground_blueprint(bp, blueprint_texts(bp), V, source_numbers, languages=("en",))
    assert ev.total("fa") == 0 and ev.total("en") == 18
    assert set(ev.to_dict()) == {"statements", "weights"}
