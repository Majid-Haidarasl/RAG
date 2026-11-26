"""Phase 13 proposal registry model and the JSON reader."""

from decimal import Decimal

import pytest

from rag_core.proposals.domain.model import Decision, ProposalRecord, ProposalRegistry
from rag_core.proposals.infrastructure.registry_json import (
    load_registry,
    registry_from_dict,
)
from rag_core.shared_kernel.errors import InvariantError
from tests.fixtures.rfp.samples import PROPOSAL_DIR, raw_registry

pytestmark = [pytest.mark.proposals]


def test_shipped_registry() -> None:
    reg = load_registry(PROPOSAL_DIR)
    assert reg.rfp_id == "AR-RFP-1403-07" and reg.ids == ("PRP-A", "PRP-B")
    a, b = reg.get("PRP-A"), reg.get("PRP-B")
    assert a is not None and b is not None and reg.get("PRP-Z") is None
    assert (a.price_mtoman, a.duration_weeks, a.published_weighted) == (
        Decimal(285),
        7,
        Decimal("78.8"),
    )
    assert (b.price_mtoman, b.duration_weeks, b.published_weighted) == (
        Decimal(240),
        5,
        Decimal("75.2"),
    )
    assert a.scores == {"CRT-TECH": Decimal(82), "CRT-FIN": Decimal(74)}
    assert b.scores == {"CRT-TECH": Decimal(68), "CRT-FIN": Decimal(86)}
    assert reg.decision is not None and reg.decision.selected == "PRP-A"


def test_language_accessors() -> None:
    reg = load_registry(PROPOSAL_DIR)
    b = reg.get("PRP-B")
    assert (
        b is not None
        and b.vendor("en") == "Novin Gozaresh Pars"
        and b.vendor("fa") == b.vendor_fa
    )
    assert b.label("fa") == "ب" and b.label("en") == "B"
    assert (
        b.feedback("en").startswith("The shorter duration")
        and len(b.clarifications("fa")) == 3
    )
    assert "AR-SW-016" in reg.decision.reason(
        "en"
    ) and "AR-SW-016" in reg.decision.reason("fa")  # type: ignore[union-attr]


def test_label_falls_back_to_the_id() -> None:
    p = ProposalRecord("PRP-X", "Vendor", "فروشنده", Decimal(1), 1, {})
    assert p.label("en") == "PRP-X" and p.published_weighted is None


def test_record_invariants() -> None:
    for changes, message in [
        ({"proposal_id": ""}, "proposal id"),
        ({"vendor_fa": " "}, "vendor_fa"),
        ({"price_mtoman": Decimal(0)}, "price"),
        ({"duration_weeks": 0}, "duration"),
    ]:
        args = {
            "proposal_id": "PRP-X",
            "vendor_en": "V",
            "vendor_fa": "و",
            "price_mtoman": Decimal(10),
            "duration_weeks": 2,
            "scores": {},
            **changes,
        }
        with pytest.raises(InvariantError, match=message):
            ProposalRecord(**args)  # type: ignore[arg-type]


def test_registry_and_decision_invariants() -> None:
    with pytest.raises(InvariantError, match="rfp_id"):
        ProposalRegistry("")
    with pytest.raises(InvariantError, match="selected"):
        Decision("")


def test_reader_rejects_unknown_keys() -> None:
    for where in ("top", "proposal", "decision"):
        raw = raw_registry()
        target = {
            "top": raw,
            "proposal": raw["proposals"][0],
            "decision": raw["decision"],
        }[where]
        target["bonus"] = 1
        with pytest.raises(InvariantError, match="unknown keys bonus"):
            registry_from_dict(raw)


def test_reader_rejects_other_schema_and_reads_missing_decision() -> None:
    raw = raw_registry()
    raw["schema_version"] = 3
    with pytest.raises(InvariantError, match="schema_version"):
        registry_from_dict(raw)
    raw = raw_registry()
    del raw["decision"]
    assert registry_from_dict(raw).decision is None
