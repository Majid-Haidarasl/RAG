"""Referral capacity ledger (AR-EXE-023 §1 and §3).

* A published ceiling is a weekly maximum for referral work. Booking beyond
  it is refused: the relevant VP must set priorities, and extra work must
  not be hidden by silently raising the ceiling.
* "No fixed hours published" (three administrative roles) means neither zero
  nor unlimited: bookings are accepted but flagged for unit planning.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rag_core.executors.domain.model import Executor
from rag_core.shared_kernel.errors import InvariantError, NotFoundError


class CapacityExceeded(InvariantError):
    """The booking would pass the published weekly referral ceiling."""


@dataclass(frozen=True)
class Booking:
    executor_id: str
    item_id: str
    hours: int
    needs_unit_planning: bool = False


@dataclass
class CapacityLedger:
    executors: dict[str, Executor]
    bookings: list[Booking] = field(default_factory=list)

    @classmethod
    def of(cls, executors: list[Executor]) -> CapacityLedger:
        return cls({str(e.identifier): e for e in executors})

    def _executor(self, executor_id: str) -> Executor:
        try:
            return self.executors[executor_id]
        except KeyError:
            raise NotFoundError(f"unknown executor {executor_id}") from None

    def booked(self, executor_id: str) -> int:
        self._executor(executor_id)
        return sum(b.hours for b in self.bookings if b.executor_id == executor_id)

    def remaining(self, executor_id: str) -> int | None:
        ceiling = self._executor(executor_id).capacity.hours_per_week
        return None if ceiling is None else ceiling - self.booked(executor_id)

    def book(self, executor_id: str, item_id: str, hours: int) -> Booking:
        if hours <= 0:
            raise InvariantError("booked hours must be positive")
        executor = self._executor(executor_id)
        ceiling = executor.capacity.hours_per_week
        if ceiling is not None and self.booked(executor_id) + hours > ceiling:
            raise CapacityExceeded(
                f"{executor_id}: {self.booked(executor_id)} + {hours} h exceeds the {ceiling} h/week referral ceiling; "
                "the relevant VP must set priorities"
            )
        booking = Booking(
            executor_id, item_id, hours, needs_unit_planning=ceiling is None
        )
        self.bookings.append(booking)
        return booking
