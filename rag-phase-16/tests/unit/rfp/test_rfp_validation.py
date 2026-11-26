"""Phase 13 blueprint validation: every name must exist, weights must add up, sections complete."""

from dataclasses import replace
from decimal import Decimal

import pytest

from rag_core.rfp.domain.validation import BlueprintValidator
from tests.fixtures.rfp.samples import (
    DOCS,
    EXECUTORS,
    ISSUES,
    NODES,
    shipped_blueprint,
    with_criterion,
    with_link,
    with_requirement,
    without_requirement,
)

pytestmark = [pytest.mark.rfp_gen]


def validator(**changes: object) -> BlueprintValidator:
    args = {
        "nodes": NODES,
        "documents": DOCS,
        "issues": ISSUES,
        "executors": EXECUTORS,
        **changes,
    }
    return BlueprintValidator(**args)  # type: ignore[arg-type]


def codes(bp, v: BlueprintValidator | None = None) -> list[str]:
    return [p.code for p in (v or validator()).validate_one(bp)]


def test_shipped_blueprint_is_valid() -> None:
    assert validator().validate([shipped_blueprint()]) == []


def test_unknown_owner_node() -> None:
    problems = validator().validate_one(
        replace(shipped_blueprint(), owner_node="N-XXX")
    )
    assert [str(p) for p in problems] == ["unknown_node:BP-WEB-REPORTING"]


def test_unknown_issue_and_item() -> None:
    bp = replace(shipped_blueprint(), issues=("AR-ISS-024", "AR-ISS-035", "AR-ISS-099"))
    assert codes(bp) == ["unknown_issue"]
    assert codes(
        shipped_blueprint(), validator(issues={"AR-ISS-024", "AR-ISS-035"})
    ) == ["unknown_item"]


def test_unknown_reference_document() -> None:
    assert codes(replace(shipped_blueprint(), reference_document="AR-RFP-099")) == [
        "unknown_document"
    ]


def test_weights_must_sum_to_one() -> None:
    bp = with_criterion(shipped_blueprint(), "CRT-FIN", weight=Decimal("0.5"))
    problems = validator().validate_one(bp)
    assert [p.code for p in problems] == ["weights_not_one"] and "1.1" in problems[
        0
    ].message


def test_missing_mandatory_section() -> None:
    bp = without_requirement(shipped_blueprint(), "REQ-ACCEPTANCE")
    found = codes(bp)
    assert (
        "missing_section" in found and "unknown_requirement" in found
    )  # LNK-INTERFACE / LNK-DESIGN point at it


def test_requirement_evidence_problems() -> None:
    fabricated = with_requirement(
        shipped_blueprint(), "REQ-SCOPE", evidence=("AR-RFP-025", "AR-XYZ-999")
    )
    assert codes(fabricated) == ["unknown_document"]
    empty = with_requirement(shipped_blueprint(), "REQ-SCOPE", evidence=())
    assert codes(empty) == ["missing_evidence"]


def test_missing_statement_in_one_language() -> None:
    assert codes(
        with_requirement(shipped_blueprint(), "REQ-NEED", statement_fa="")
    ) == ["missing_statement"]


def test_executor_on_another_node_or_unknown() -> None:
    wrong = with_link(shipped_blueprint(), "LNK-DESIGN", executor="EX-REZA-ABBASI")
    problems = validator().validate_one(wrong)
    assert [p.code for p in problems] == [
        "executor_node_mismatch"
    ] and "N-ADM-FIN" in problems[0].message
    assert codes(
        with_link(shipped_blueprint(), "LNK-DESIGN", executor="EX-NOBODY")
    ) == ["unknown_executor"]


def test_link_to_unknown_node_or_requirement() -> None:
    assert codes(with_link(shipped_blueprint(), "LNK-LIBRARY", node="N-XYZ")) == [
        "unknown_node"
    ]
    assert codes(
        with_link(shipped_blueprint(), "LNK-LIBRARY", requirements=("REQ-NOPE",))
    ) == ["unknown_requirement"]


def test_duplicate_ids() -> None:
    bp = shipped_blueprint()
    dup = replace(bp, requirements=bp.requirements + (bp.requirements[0],))
    assert codes(dup) == ["duplicate_requirement"]
    found = [p.code for p in validator().validate([bp, bp])]
    assert found == ["duplicate_blueprint", "duplicate_rfp"]
