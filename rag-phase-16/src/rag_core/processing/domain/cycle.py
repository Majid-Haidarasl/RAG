"""ProcessingCycle value object and the per-step / per-cycle reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import re
from typing import Any

from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.numerals import normalize_digits

_CYCLE_RE = re.compile(r"^\d{4}-(?:Q[1-4]|M(?:0[1-9]|1[0-2]))$")


@dataclass(frozen=True)
class ProcessingCycle:
    """One processing period: ``1403-Q2`` (quarter) or ``1403-M06`` (month), Jalali year."""

    cycle_id: str
    period_end: str = ""
    trigger: str = ""

    def __post_init__(self) -> None:
        text = normalize_digits(self.cycle_id.strip()).upper()
        if not _CYCLE_RE.match(text):
            raise InvariantError(
                f"invalid cycle id {self.cycle_id!r} (use e.g. 1403-Q2 or 1403-M06)"
            )
        object.__setattr__(self, "cycle_id", text)

    @property
    def year(self) -> int:
        return int(self.cycle_id[:4])

    @property
    def period(self) -> str:
        return self.cycle_id[5:]

    def __str__(self) -> str:
        return self.cycle_id


class StepOutcome(StrEnum):
    BUILT = "built"
    FAILED = "failed"


@dataclass(frozen=True)
class StepResult:
    order: int
    source_node: str
    target_node: str
    target_layer: int
    outcome: StepOutcome
    status: str = ""  # accepted | rejected (package status)
    detail_level: str = ""
    store_action: str = ""  # inserted | unchanged | updated | ""
    revision: int | None = None
    received: int = 0
    expected_children: int = 0
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "order": self.order,
            "source_node": self.source_node,
            "target_node": self.target_node,
            "target_layer": self.target_layer,
            "outcome": self.outcome.value,
            "status": self.status,
            "detail_level": self.detail_level,
            "store_action": self.store_action,
            "revision": self.revision,
            "received": self.received,
            "expected_children": self.expected_children,
            "reason": self.reason,
        }


@dataclass
class CycleReport:
    cycle_id: str
    steps: list[StepResult] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        built = [s for s in self.steps if s.outcome is StepOutcome.BUILT]
        return {
            "steps": len(self.steps),
            "built": len(built),
            "failed": sum(1 for s in self.steps if s.outcome is StepOutcome.FAILED),
            "accepted": sum(1 for s in built if s.status == "accepted"),
            "rejected": sum(1 for s in built if s.status == "rejected"),
            "inserted": sum(1 for s in self.steps if s.store_action == "inserted"),
            "unchanged": sum(1 for s in self.steps if s.store_action == "unchanged"),
            "updated": sum(1 for s in self.steps if s.store_action == "updated"),
            "skipped": len(self.skipped),
        }

    def by_layer(self) -> dict[int, int]:
        out: dict[int, int] = {}
        for s in self.steps:
            out[s.target_layer] = out.get(s.target_layer, 0) + 1
        return dict(sorted(out.items()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "counts": self.counts(),
            "steps": [s.to_dict() for s in self.steps],
            "skipped": [{"node": n, "reason": r} for n, r in self.skipped],
        }
