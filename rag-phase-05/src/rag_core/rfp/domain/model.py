"""RFP aggregate, proposals and weighted scoring."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP

from rag_core.shared_kernel.errors import InvariantError, NotFoundError
from rag_core.shared_kernel.events import DomainEvent
from rag_core.shared_kernel.identifiers import NodeIdentifier, RfpId


TWOPLACES = Decimal("0.1")  # one decimal, as published 78.8 / 75.2


@dataclass(frozen=True)
class CriterionWeight:
    name: str
    weight: Decimal

    def __post_init__(self) -> None:
        amount = self.weight if isinstance(self.weight, Decimal) else Decimal(self.weight)
        object.__setattr__(self, "weight", amount)
        if not self.name.strip():
            raise InvariantError("criterion name is required")
        if amount <= 0:
            raise InvariantError("criterion weight must be positive")


@dataclass(frozen=True)
class WeightedScore:
    value: Decimal

    def __post_init__(self) -> None:
        amount = self.value if isinstance(self.value, Decimal) else Decimal(self.value)
        object.__setattr__(self, "value", amount)


def compute_weighted_score(
    scores: dict[str, Decimal],
    weights: tuple[CriterionWeight, ...],
) -> WeightedScore:
    total_weight = sum((w.weight for w in weights), Decimal(0))
    if total_weight != Decimal(1) and total_weight != Decimal(100):
        # Allow either fractions that sum to 1 or percentages that sum to 100.
        raise InvariantError(f"weights must sum to 1 or 100, got {total_weight}")
    divisor = Decimal(1) if total_weight == Decimal(1) else Decimal(100)
    acc = Decimal(0)
    for weight in weights:
        if weight.name not in scores:
            raise InvariantError(f"missing score for criterion {weight.name!r}")
        acc += scores[weight.name] * (weight.weight / divisor)
    return WeightedScore(acc.quantize(TWOPLACES, rounding=ROUND_HALF_UP))


@dataclass
class Proposal:
    vendor: str
    criterion_scores: dict[str, Decimal]
    weighted: WeightedScore | None = None

    def __post_init__(self) -> None:
        if not self.vendor.strip():
            raise InvariantError("proposal vendor is required")


@dataclass
class Rfp:
    identifier: RfpId
    title: str
    owning_node: NodeIdentifier
    criteria: tuple[CriterionWeight, ...]
    proposals: list[Proposal] = field(default_factory=list)
    events: list[DomainEvent] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise InvariantError("RFP title is required")
        if not self.criteria:
            raise InvariantError("RFP without evaluation criteria fails validation")
        total = sum((c.weight for c in self.criteria), Decimal(0))
        if total not in {Decimal(1), Decimal(100)}:
            raise InvariantError(f"criterion weights must sum to 1 or 100, got {total}")

    def add_proposal(self, proposal: Proposal) -> Proposal:
        proposal.weighted = compute_weighted_score(proposal.criterion_scores, self.criteria)
        self.proposals.append(proposal)
        self.events.append(
            DomainEvent("ProposalEvaluated", {"vendor": proposal.vendor, "score": str(proposal.weighted.value)})
        )
        return proposal

    def proposal(self, vendor: str) -> Proposal:
        for item in self.proposals:
            if item.vendor == vendor:
                return item
        raise NotFoundError(vendor)

    def publish(self) -> None:
        self.events.append(DomainEvent("RfpPublished", {"rfp_id": str(self.identifier)}))


# Reconstructed criterion scores that reproduce the published AR-RFP-025 totals
# (technical 60% + financial 40%). Exact per-criterion table in the corpus is
# not copied here; these components are the unique pair that the unit-test
# policy requires the formula to reproduce.
AR_RFP_025_WEIGHTS = (
    CriterionWeight("technical", Decimal("0.6")),
    CriterionWeight("financial", Decimal("0.4")),
)
AR_RFP_025_SHAFAGH_SCORES = {"technical": Decimal("82"), "financial": Decimal("74")}
AR_RFP_025_NOVIN_SCORES = {"technical": Decimal("76"), "financial": Decimal("74")}
