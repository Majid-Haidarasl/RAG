"""Proposal registry: registered bidder proposals for one RFP and the recorded decision."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal

from rag_core.shared_kernel.errors import InvariantError


def _required(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise InvariantError(f"{name} is required")
    return text


@dataclass(frozen=True)
class ProposalRecord:
    proposal_id: str
    vendor_en: str
    vendor_fa: str
    price_mtoman: Decimal  # million toman, as written in the evaluation sheet
    duration_weeks: int
    scores: Mapping[str, Decimal]  # criterion id -> 0..100
    label_en: str = ""
    label_fa: str = ""
    technology: str = ""
    version: str = "1.0"
    published_weighted: Decimal | None = None
    sections: tuple[str, ...] = ()
    clarifications_en: tuple[str, ...] = ()
    clarifications_fa: tuple[str, ...] = ()
    feedback_en: str = ""
    feedback_fa: str = ""
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _required(self.proposal_id, "proposal id")
        _required(self.vendor_en, f"{self.proposal_id}: vendor_en")
        _required(self.vendor_fa, f"{self.proposal_id}: vendor_fa")
        price = Decimal(str(self.price_mtoman))
        if price <= 0:
            raise InvariantError(f"{self.proposal_id}: price must be positive")
        if int(self.duration_weeks) <= 0:
            raise InvariantError(f"{self.proposal_id}: duration must be positive")
        object.__setattr__(self, "price_mtoman", price)
        object.__setattr__(self, "duration_weeks", int(self.duration_weeks))
        object.__setattr__(
            self,
            "scores",
            {str(k): Decimal(str(v)) for k, v in dict(self.scores).items()},
        )
        if self.published_weighted is not None:
            object.__setattr__(
                self, "published_weighted", Decimal(str(self.published_weighted))
            )
        for name in ("sections", "clarifications_en", "clarifications_fa", "evidence"):
            object.__setattr__(self, name, tuple(str(v) for v in getattr(self, name)))

    def vendor(self, language: str) -> str:
        return self.vendor_fa if language == "fa" else self.vendor_en

    def label(self, language: str) -> str:
        return (
            self.label_fa if language == "fa" else self.label_en
        ) or self.proposal_id

    def feedback(self, language: str) -> str:
        return self.feedback_fa if language == "fa" else self.feedback_en

    def clarifications(self, language: str) -> tuple[str, ...]:
        return self.clarifications_fa if language == "fa" else self.clarifications_en


@dataclass(frozen=True)
class Decision:
    selected: str
    reason_en: str = ""
    reason_fa: str = ""
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _required(self.selected, "decision.selected")
        object.__setattr__(self, "evidence", tuple(self.evidence))

    def reason(self, language: str) -> str:
        return self.reason_fa if language == "fa" else self.reason_en


@dataclass(frozen=True)
class ProposalRegistry:
    rfp_id: str
    proposals: tuple[ProposalRecord, ...] = field(default_factory=tuple)
    decision: Decision | None = None

    def __post_init__(self) -> None:
        _required(self.rfp_id, "registry rfp_id")
        object.__setattr__(self, "proposals", tuple(self.proposals))

    def get(self, proposal_id: str) -> ProposalRecord | None:
        return next((p for p in self.proposals if p.proposal_id == proposal_id), None)

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(p.proposal_id for p in self.proposals)
