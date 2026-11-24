"""Phase 13 proposal registry validation against the RFP blueprint."""

import pytest

from rag_core.proposals.domain.validation import ProposalValidator
from rag_core.proposals.infrastructure.registry_json import registry_from_dict
from tests.fixtures.rfp.samples import DOCS, raw_registry, shipped_blueprint

pytestmark = [pytest.mark.proposals]


def problems(raw: dict) -> list[str]:
    return [
        str(p)
        for p in ProposalValidator([shipped_blueprint()], DOCS).validate(
            registry_from_dict(raw)
        )
    ]


def prp(raw: dict, pid: str) -> dict:
    return next(p for p in raw["proposals"] if p["id"] == pid)


def test_shipped_registry_is_valid() -> None:
    assert problems(raw_registry()) == []


def test_unknown_rfp() -> None:
    raw = raw_registry()
    raw["rfp_id"] = "AR-RFP-1403-99"
    assert problems(raw) == ["unknown_rfp:AR-RFP-1403-99"]


def test_duplicate_proposal() -> None:
    raw = raw_registry()
    raw["proposals"].append(raw["proposals"][0])
    assert problems(raw) == ["duplicate_id:PRP-A"]


def test_scores_must_match_the_criteria() -> None:
    raw = raw_registry()
    prp(raw, "PRP-A")["scores"]["CRT-API"] = "90"
    del prp(raw, "PRP-B")["scores"]["CRT-FIN"]
    assert problems(raw) == [
        "unknown_criterion:PRP-A/CRT-API",
        "missing_score:PRP-B/CRT-FIN",
    ]


def test_score_range() -> None:
    raw = raw_registry()
    prp(raw, "PRP-B")["scores"]["CRT-TECH"] = "110"
    assert problems(raw) == ["score_range:PRP-B/CRT-TECH"]


def test_response_sections() -> None:
    raw = raw_registry()
    prp(raw, "PRP-B")["sections"].remove("test_plan")
    prp(raw, "PRP-A")["sections"].append("slides")
    assert problems(raw) == [
        "unknown_section:PRP-A/slides",
        "missing_section:PRP-B/test_plan",
    ]


def test_evidence_documents() -> None:
    raw = raw_registry()
    prp(raw, "PRP-A")["evidence"] = []
    prp(raw, "PRP-B")["evidence"] = ["AR-XYZ-999"]
    assert problems(raw) == ["missing_evidence:PRP-A", "unknown_document:PRP-B"]


def test_decision_problems() -> None:
    raw = raw_registry()
    raw["decision"]["selected"] = "PRP-Z"
    assert problems(raw) == ["decision_unknown:PRP-Z"]
    raw = raw_registry()
    del raw["decision"]
    assert problems(raw) == ["decision_missing:AR-RFP-1403-07"]
