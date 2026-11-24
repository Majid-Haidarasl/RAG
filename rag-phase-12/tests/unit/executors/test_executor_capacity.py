"""Capacity ledger: published ceilings refuse overbooking; unpublished ones need unit planning."""

import pytest

from rag_core.executors.domain.capacity import CapacityExceeded, CapacityLedger
from rag_core.shared_kernel.errors import InvariantError, NotFoundError
from tests.fixtures.executors.registry import make_executor

pytestmark = [pytest.mark.executors, pytest.mark.matching]


def _ledger() -> CapacityLedger:
    return CapacityLedger.of(
        [
            make_executor("EX-SAEED-AKBARI", "Saeed Akbari", "N-HW-REP", hours=32),
            make_executor("EX-MAHSA-JALALI", "Mahsa Jalali", "N-ADM-LEG", hours=None),
        ]
    )


def test_booking_within_ceiling() -> None:
    ledger = _ledger()
    ledger.book("EX-SAEED-AKBARI", "AR-ISS-024/HW", 20)
    ledger.book("EX-SAEED-AKBARI", "AR-ISS-031", 12)
    assert (
        ledger.booked("EX-SAEED-AKBARI") == 32
        and ledger.remaining("EX-SAEED-AKBARI") == 0
    )


def test_overbooking_is_refused_and_sent_to_the_vp() -> None:
    ledger = _ledger()
    ledger.book("EX-SAEED-AKBARI", "AR-ISS-024/HW", 30)
    with pytest.raises(CapacityExceeded, match="VP must set priorities"):
        ledger.book("EX-SAEED-AKBARI", "AR-ISS-031", 3)
    assert ledger.booked("EX-SAEED-AKBARI") == 30


def test_unpublished_capacity_is_booked_with_unit_planning_flag() -> None:
    ledger = _ledger()
    booking = ledger.book("EX-MAHSA-JALALI", "AR-ISS-024/LEG", 40)
    assert booking.needs_unit_planning
    assert ledger.remaining("EX-MAHSA-JALALI") is None


def test_invalid_bookings() -> None:
    ledger = _ledger()
    with pytest.raises(InvariantError):
        ledger.book("EX-SAEED-AKBARI", "AR-ISS-024/HW", 0)
    with pytest.raises(NotFoundError):
        ledger.book("EX-NOBODY-HERE", "AR-ISS-024/HW", 2)
