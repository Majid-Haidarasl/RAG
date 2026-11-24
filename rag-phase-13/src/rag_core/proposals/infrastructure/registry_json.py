"""``data/proposals/proposal-registry.json`` -> ``ProposalRegistry`` (unknown keys are rejected)."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from rag_core.proposals.domain.model import Decision, ProposalRecord, ProposalRegistry
from rag_core.shared_kernel.errors import InvariantError

FILE_NAME = "proposal-registry.json"
TOP_KEYS = {"schema_version", "note", "rfp_id", "proposals", "decision"}
PROPOSAL_KEYS = {
    "id",
    "label_en",
    "label_fa",
    "vendor_en",
    "vendor_fa",
    "price_mtoman",
    "duration_weeks",
    "technology",
    "version",
    "scores",
    "published_weighted",
    "sections",
    "clarifications_en",
    "clarifications_fa",
    "feedback_en",
    "feedback_fa",
    "evidence",
}
DECISION_KEYS = {"selected", "reason_en", "reason_fa", "evidence"}


def _check(rec: Any, allowed: set[str], where: str) -> dict:
    if not isinstance(rec, dict):
        raise InvariantError(f"{where} must be an object")
    unknown = sorted(set(rec) - allowed)
    if unknown:
        raise InvariantError(f"{where}: unknown keys {', '.join(unknown)}")
    return rec


def proposal_from(rec: dict) -> ProposalRecord:
    rec = _check(rec, PROPOSAL_KEYS, "proposal")
    scores = rec.get("scores") or {}
    if not isinstance(scores, dict):
        raise InvariantError(f"{rec.get('id', '?')}: scores must be an object")
    published = rec.get("published_weighted")
    return ProposalRecord(
        proposal_id=str(rec.get("id", "")),
        vendor_en=str(rec.get("vendor_en", "")),
        vendor_fa=str(rec.get("vendor_fa", "")),
        price_mtoman=Decimal(str(rec.get("price_mtoman", "0"))),
        duration_weeks=int(rec.get("duration_weeks", 0)),
        scores={k: Decimal(str(v)) for k, v in scores.items()},
        label_en=str(rec.get("label_en", "")),
        label_fa=str(rec.get("label_fa", "")),
        technology=str(rec.get("technology", "")),
        version=str(rec.get("version", "1.0")),
        published_weighted=Decimal(str(published))
        if published not in (None, "")
        else None,
        sections=tuple(rec.get("sections") or ()),
        clarifications_en=tuple(rec.get("clarifications_en") or ()),
        clarifications_fa=tuple(rec.get("clarifications_fa") or ()),
        feedback_en=str(rec.get("feedback_en", "")),
        feedback_fa=str(rec.get("feedback_fa", "")),
        evidence=tuple(rec.get("evidence") or ()),
    )


def registry_from_dict(data: dict) -> ProposalRegistry:
    data = _check(data, TOP_KEYS, "proposal registry")
    if int(data.get("schema_version", 1)) != 1:
        raise InvariantError("unsupported proposal registry schema_version")
    raw_decision = data.get("decision")
    decision = None
    if raw_decision is not None:
        d = _check(raw_decision, DECISION_KEYS, "decision")
        decision = Decision(
            str(d.get("selected", "")),
            str(d.get("reason_en", "")),
            str(d.get("reason_fa", "")),
            tuple(d.get("evidence") or ()),
        )
    return ProposalRegistry(
        str(data.get("rfp_id", "")),
        tuple(proposal_from(p) for p in data.get("proposals") or ()),
        decision,
    )


def read_registry_dict(folder: Path) -> dict:
    return json.loads((Path(folder) / FILE_NAME).read_text(encoding="utf-8"))


def load_registry(folder: Path) -> ProposalRegistry:
    return registry_from_dict(read_registry_dict(folder))
