"""LayerIndex value object — integer position of a hierarchy layer; 0 is the top."""

from __future__ import annotations

from dataclasses import dataclass

from rag_core.shared_kernel.errors import InvariantError


@dataclass(frozen=True, order=True)
class LayerIndex:
    """ArmanRayan uses 0–4. The type allows 0–9 so a future corpus can add a layer."""

    value: int

    def __post_init__(self) -> None:
        if not isinstance(self.value, int) or isinstance(self.value, bool):
            raise InvariantError(f"LayerIndex must be an int, got {self.value!r}")
        if self.value < 0 or self.value > 9:
            raise InvariantError(f"LayerIndex out of range: {self.value}")

    def __str__(self) -> str:
        return f"L{self.value}"

    @property
    def code(self) -> str:
        return f"L{self.value}"

    def is_adjacent_parent_of(self, child: LayerIndex) -> bool:
        return self.value == child.value - 1
