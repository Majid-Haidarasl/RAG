"""Phase 13 proposal use case: audit, evaluation problems and the shipped negative controls."""

import copy

import pytest

from rag_core.proposals.application.services import ProposalService, evaluation_problems
from rag_core.proposals.domain.evaluation import evaluate
from rag_core.proposals.infrastructure.registry_json import registry_from_dict
from rag_core.qa.domain.fact_check import CitedFactValidator, source_numbers
from tests.fixtures.rfp.samples import (
    DOCS,
    EXECUTORS,
    NODES,
    raw_registry,
    registry_texts,
    shipped_blueprint,
    shipped_registry,
)

pytestmark = [pytest.mark.proposals]


def service() -> ProposalService:
    return ProposalService(
        [shipped_blueprint()],
        DOCS,
        registry_texts(shipped_registry()),
        CitedFactValidator(),
        source_numbers,
    )


def prp(raw: dict, pid: str) -> dict:
    return next(p for p in raw["proposals"] if p["id"] == pid)


def test_shipped_registry_passes_the_audit() -> None:
    audit = service().audit(shipped_registry())
    assert audit.ok and audit.codes == [] and audit.evaluation is not None
    assert audit.evaluation.decision_consistent and audit.to_dict()["ok"] is True


def _price_formula(d: dict) -> None:
    prp(d, "PRP-A")["scores"]["CRT-FIN"] = "84.2"


def _wrong_price(d: dict) -> None:
    prp(d, "PRP-B")["price_mtoman"] = 250


def _subscore(d: dict) -> None:
    prp(d, "PRP-A")["scores"]["CRT-API"] = "90"


def _missing_score(d: dict) -> None:
    del prp(d, "PRP-A")["scores"]["CRT-FIN"]


def _range(d: dict) -> None:
    prp(d, "PRP-B")["scores"]["CRT-TECH"] = "110"


def _section(d: dict) -> None:
    prp(d, "PRP-B")["sections"].remove("test_plan")


def _decision(d: dict) -> None:
    d["decision"]["selected"] = "PRP-B"


def _rfp(d: dict) -> None:
    d["rfp_id"] = "AR-RFP-1403-99"


def _duplicate(d: dict) -> None:
    d["proposals"].append(copy.deepcopy(d["proposals"][0]))


def _feedback(d: dict) -> None:
    prp(d, "PRP-B")["feedback_en"] += " Its score was 91."


@pytest.mark.parametrize(
    "change, code",
    [
        (_price_formula, "published_mismatch"),
        (_wrong_price, "ungrounded_number"),
        (_subscore, "unknown_criterion"),
        (_missing_score, "missing_score"),
        (_range, "score_range"),
        (_section, "missing_section"),
        (_decision, "decision_mismatch"),
        (_rfp, "unknown_rfp"),
        (_duplicate, "duplicate_id"),
        (_feedback, "ungrounded_statement"),
    ],
)
def test_negative_controls_are_rejected_for_the_right_reason(change, code: str) -> None:  # noqa: ANN001
    raw = raw_registry()
    change(raw)
    audit = service().audit(registry_from_dict(raw))
    assert not audit.ok and code in audit.codes, audit.codes


def test_evaluation_problems_without_a_winner() -> None:
    raw = raw_registry()
    for p in raw["proposals"]:
        p["sections"] = []
    e = evaluate(shipped_blueprint(), registry_from_dict(raw))
    assert [p.code for p in evaluation_problems(e)] == ["no_winner"]


def test_feedback_and_knowledge_through_the_service() -> None:
    s = service()
    reg = shipped_registry()
    audit = s.audit(reg)
    fb = s.feedback(reg, audit.evaluation)  # type: ignore[arg-type]
    assert set(fb) == {"PRP-A", "PRP-B"} and set(fb["PRP-B"]) == {"fa", "en"}
    k = s.knowledge(reg, audit.evaluation, NODES, EXECUTORS)  # type: ignore[arg-type]
    assert k is not None and k.ok


def test_unknown_rfp_gives_no_feedback_or_knowledge() -> None:
    raw = raw_registry()
    raw["rfp_id"] = "AR-RFP-1403-99"
    reg = registry_from_dict(raw)
    s = service()
    audit = s.audit(reg)
    assert (
        audit.evaluation is None
        and s.knowledge(reg, evaluate(shipped_blueprint(), reg), NODES, EXECUTORS)
        is None
    )
    assert s.feedback(reg, evaluate(shipped_blueprint(), reg)) == {}
