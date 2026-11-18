"""Per-layer knowledge-transfer requirements (AR-TRN-026 §6, AR-BRD-003, AR-ORG-002)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.layer import LayerIndex

MIN_ARTEFACTS = 2
MIN_APPROVALS = 1


class TransferDirection(StrEnum):
    UP = "up"  # to the parent layer (L1–L3)
    DOWN = "down"  # Board resolutions to L1
    PEER = "peer"  # L4 library with L3: indexing and links, no upward summary


@dataclass(frozen=True)
class TransferRequirement:
    """What a layer must hand over, to whom, with which artefacts and approvals."""

    layer: LayerIndex
    direction: TransferDirection
    target: LayerIndex
    must_hand_over: str
    min_artefacts: tuple[str, ...]
    approvals: tuple[str, ...]
    required_feedback: str
    sources: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.direction is TransferDirection.UP and self.target.value != self.layer.value - 1:
            raise InvariantError(f"{self.layer} hands over upward only to L{self.layer.value - 1}")
        if self.direction is TransferDirection.DOWN and self.target.value != self.layer.value + 1:
            raise InvariantError(f"{self.layer} hands down only to L{self.layer.value + 1}")
        if self.target == self.layer:
            raise InvariantError("a layer cannot transfer to itself")

    def gaps(self) -> list[str]:
        """Missing parts; an empty list means the requirement is complete."""
        missing: list[str] = []
        if not self.must_hand_over.strip():
            missing.append("must_hand_over")
        if len([a for a in self.min_artefacts if a.strip()]) < MIN_ARTEFACTS:
            missing.append(f"min_artefacts<{MIN_ARTEFACTS}")
        if len([a for a in self.approvals if a.strip()]) < MIN_APPROVALS:
            missing.append("approvals")
        if not self.required_feedback.strip():
            missing.append("required_feedback")
        if not self.sources:
            missing.append("sources")
        return missing

    @property
    def is_complete(self) -> bool:
        return not self.gaps()

    def check_package(self, artefacts: set[str], approvals: set[str]) -> list[str]:
        """Which minimum artefacts / approvals a concrete hand-over still lacks."""
        missing = [f"artefact: {a}" for a in self.min_artefacts if a not in artefacts]
        missing += [f"approval: {a}" for a in self.approvals if a not in approvals]
        return missing
