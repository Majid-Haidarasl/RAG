"""TransferPackage and per-layer TransferRuleSet."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from rag_core.knowledge.domain.services import Citation
from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.events import DomainEvent
from rag_core.shared_kernel.identifiers import NodeIdentifier
from rag_core.shared_kernel.layer import LayerIndex


class TransferDetailLevel(StrEnum):
    EXECUTIVE = "executive"
    MANAGERIAL = "managerial"
    TECHNICAL_SUMMARY = "technical_summary"
    DETAILED_TECHNICAL = "detailed_technical"


class PackageStatus(StrEnum):
    DRAFT = "draft"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


# L0 (executive) packages must include these fields (policy item 12, AR-TRN-026).
L0_REQUIRED_FIELDS = ("risks", "decisions_requested", "source_references")


@dataclass(frozen=True)
class TransferTrigger:
    name: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise InvariantError("trigger name is required")


@dataclass
class TransferRuleSet:
    layer: LayerIndex
    detail_level: TransferDetailLevel
    min_judge_score: int = 18
    max_words: int | None = None
    required_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.layer.value == 0 and not self.required_fields:
            object.__setattr__(self, "required_fields", L0_REQUIRED_FIELDS)
        if self.min_judge_score < 0 or self.min_judge_score > 20:
            raise InvariantError("min_judge_score must be in [0, 20]")


@dataclass
class TransferPackage:
    source_node: NodeIdentifier
    target_node: NodeIdentifier
    target_layer: LayerIndex
    detail_level: TransferDetailLevel
    fields: dict[str, str]
    citations: tuple[Citation, ...] = ()
    status: PackageStatus = PackageStatus.DRAFT
    events: list[DomainEvent] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.source_node == self.target_node:
            raise InvariantError("a package cannot be sent to its own node")

    @classmethod
    def assemble(
        cls,
        *,
        source_node: NodeIdentifier,
        target_node: NodeIdentifier,
        rules: TransferRuleSet,
        fields: dict[str, str],
        citations: list[Citation],
    ) -> TransferPackage:
        missing = [name for name in rules.required_fields if not str(fields.get(name, "")).strip()]
        if missing:
            raise InvariantError(f"TransferPackage missing required fields: {missing}")
        # source_references may be represented by citations when the field is present.
        if "source_references" in rules.required_fields and not citations:
            raise InvariantError("L0/required packages need source citations")
        if rules.max_words is not None:
            words = sum(len(v.split()) for v in fields.values())
            if words > rules.max_words:
                raise InvariantError(f"package has {words} words, max is {rules.max_words}")
        package = cls(
            source_node=source_node,
            target_node=target_node,
            target_layer=rules.layer,
            detail_level=rules.detail_level,
            fields=dict(fields),
            citations=tuple(citations),
        )
        package.events.append(
            DomainEvent("CycleCompleted", {"source": str(source_node), "target": str(target_node)})
        )
        return package

    def accept(self) -> None:
        if self.status is not PackageStatus.DRAFT:
            raise InvariantError("only a draft package can be accepted")
        self.status = PackageStatus.ACCEPTED
        self.events.append(DomainEvent("PackageAccepted", {"source": str(self.source_node)}))

    def reject(self, reason: str) -> None:
        if self.status is not PackageStatus.DRAFT:
            raise InvariantError("only a draft package can be rejected")
        self.status = PackageStatus.REJECTED
        self.events.append(DomainEvent("PackageRejected", {"reason": reason}))
