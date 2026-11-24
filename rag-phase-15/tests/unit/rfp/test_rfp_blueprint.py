"""Phase 13 RFP blueprint: the shipped blueprint and the model invariants."""

from dataclasses import replace
from decimal import Decimal
import re

import pytest

from rag_core.rfp.domain.blueprint import (
    MANDATORY_SECTIONS,
    RESPONSE_SECTIONS,
    SECTION_ORDER,
    Criterion,
    KnowledgeLink,
    Requirement,
)
from rag_core.shared_kernel.errors import InvariantError
from tests.fixtures.rfp.samples import (
    MANDATORY,
    shipped_blueprint,
    with_requirement,
    without_requirement,
)

pytestmark = [pytest.mark.rfp_gen]


def test_shipped_blueprint_shape() -> None:
    bp = shipped_blueprint()
    assert bp.blueprint_id == "BP-WEB-REPORTING" and bp.rfp_id == "AR-RFP-1403-07"
    assert (
        bp.owner_node == "N-SW"
        and bp.item == "AR-ISS-024/WEB"
        and bp.reference_document == "AR-RFP-025"
    )
    assert bp.issues == ("AR-ISS-024", "AR-ISS-035")
    assert (len(bp.requirements), len(bp.criteria), len(bp.links)) == (11, 2, 7)


def test_weights_add_up_to_one_as_60_40() -> None:
    bp = shipped_blueprint()
    assert bp.weight_total == Decimal("1")
    assert [c.percent for c in bp.criteria] == [60, 40]
    assert [c.criterion_id for c in bp.criteria] == ["CRT-TECH", "CRT-FIN"]


def test_every_section_present_and_mandatory_ids() -> None:
    bp = shipped_blueprint()
    assert bp.sections() == SECTION_ORDER
    assert bp.missing_mandatory() == ()
    assert bp.mandatory_ids() == MANDATORY
    assert {bp.requirement(r).section.value for r in MANDATORY} == set(
        MANDATORY_SECTIONS
    )


def test_linked_ids_are_rfp_item_and_issues() -> None:
    assert shipped_blueprint().linked_ids() == (
        "AR-RFP-1403-07",
        "AR-ISS-024/WEB",
        "AR-ISS-024",
        "AR-ISS-035",
    )


def test_record_ids_carry_no_digits_so_the_fact_checker_never_reads_them_as_data() -> (
    None
):
    bp = shipped_blueprint()
    ids = [
        bp.blueprint_id,
        *(r.requirement_id for r in bp.requirements),
        *(c.criterion_id for c in bp.criteria),
        *(x.link_id for x in bp.links),
    ]
    assert all(not re.search(r"\d", i) for i in ids)


def test_answered_in_names_a_response_section() -> None:
    bp = shipped_blueprint()
    assert all(
        r.answered_in in RESPONSE_SECTIONS for r in bp.requirements if r.answered_in
    )
    assert bp.response_sections == RESPONSE_SECTIONS


def test_language_accessors() -> None:
    bp = shipped_blueprint()
    tech = bp.criterion("CRT-TECH")
    assert bp.title("en").startswith(
        "Warehouse web reporting"
    ) and "آذرپخش" in bp.title("fa")
    assert (
        tech is not None and tech.name("en") == "Technical" and tech.name("fa") == "فنی"
    )
    req = bp.requirement("REQ-EVALUATION")
    assert (
        req is not None
        and "60%" in req.statement("en")
        and req.statement("fa") == req.statement_fa
    )
    assert bp.requirement("REQ-NOPE") is None and bp.criterion("CRT-NOPE") is None


def test_dropping_a_mandatory_requirement_is_reported() -> None:
    bp = without_requirement(shipped_blueprint(), "REQ-ACCEPTANCE")
    assert bp.missing_mandatory() == ("acceptance",)


def test_an_optional_requirement_does_not_cover_a_mandatory_section() -> None:
    bp = with_requirement(shipped_blueprint(), "REQ-NEED", mandatory=False)
    assert bp.missing_mandatory() == ("need",)


def test_requirement_rejects_unknown_answer_section_and_section() -> None:
    with pytest.raises(InvariantError, match="response section"):
        Requirement("REQ-X", "need", "a", "b", answered_in="slides")
    with pytest.raises(ValueError):
        Requirement("REQ-X", "marketing", "a", "b")
    with pytest.raises(InvariantError, match="requirement id"):
        Requirement(" ", "need", "a", "b")


def test_criterion_weight_must_be_in_zero_one() -> None:
    for weight in ("0", "-0.1", "1.5"):
        with pytest.raises(InvariantError, match="weight"):
            Criterion("CRT-X", "X", "ایکس", Decimal(weight))


def test_criterion_percent_rounds_to_integer() -> None:
    assert Criterion("CRT-X", "X", "ایکس", Decimal("0.25")).percent == 25


def test_link_needs_a_node() -> None:
    with pytest.raises(InvariantError, match="node"):
        KnowledgeLink("LNK-X", "", "role", "نقش")


def test_blueprint_invariants() -> None:
    bp = shipped_blueprint()
    with pytest.raises(InvariantError, match="criteria"):
        replace(bp, criteria=())
    with pytest.raises(InvariantError, match="issue"):
        replace(bp, issues=())
    with pytest.raises(InvariantError, match="not under its issues"):
        replace(bp, item="AR-ISS-031/WEB")
    with pytest.raises(InvariantError, match="response sections"):
        replace(bp, response_sections=("pricing", "slides"))
    with pytest.raises(InvariantError, match="title"):
        replace(bp, title_fa=" ")
