"""Executor profile metadata (Phase 9): capacity, aliases, knowledge, profile changes."""

import pytest

from rag_core.executors.domain.model import ExpertiseTag, ReferralCapacity, executor_id_for
from rag_core.shared_kernel.errors import InvariantError
from tests.fixtures.executors.registry import make_executor

pytestmark = [pytest.mark.executors, pytest.mark.matching]


def test_unpublished_capacity_is_neither_zero_nor_unlimited() -> None:
    cap = ReferralCapacity.unpublished()
    assert cap.hours_per_week is None and not cap.is_published
    assert "unit planning" in cap.describe()
    assert ReferralCapacity(0).is_published and ReferralCapacity(0).describe() == "0 h/week"


@pytest.mark.parametrize("hours", [-1, 61])
def test_capacity_out_of_range_is_rejected(hours: int) -> None:
    with pytest.raises(InvariantError, match="out of range"):
        ReferralCapacity(hours)


def test_expertise_tag_is_normalized() -> None:
    assert str(ExpertiseTag("  Windows   Client ")) == "windows client"
    with pytest.raises(InvariantError):
        ExpertiseTag("   ")


def test_executor_id_follows_canonical_name() -> None:
    assert str(executor_id_for("Rouzbeh  Mohseni")) == "EX-ROOZBEH-MOHSENI"
    assert str(executor_id_for("Kamran Nikpour")) == "EX-KAMRAN-NIKPOUR"


def test_executor_answers_to_name_and_alias() -> None:
    person = make_executor("EX-ROOZBEH-MOHSENI", "Roozbeh Mohseni", "N-SW-WIN", aliases=("Rouzbeh Mohseni",))
    assert person.answers_to("roozbeh   mohseni")
    assert person.answers_to("Rouzbeh Mohseni")
    assert not person.answers_to("Saeed Akbari")


def test_holds_knowledge_documents() -> None:
    person = make_executor(docs=("AR-SW-016", "AR-SW-017"))
    assert person.holds("AR-SW-017") and not person.holds("AR-SW-019")


def test_duplicate_knowledge_document_is_rejected() -> None:
    with pytest.raises(InvariantError, match="duplicate knowledge"):
        make_executor(docs=("AR-SW-016", "AR-SW-016"))


def test_capacity_change_needs_reason_and_approval() -> None:
    person = make_executor(hours=18)
    with pytest.raises(InvariantError, match="reason"):
        person.change_capacity(ReferralCapacity(24), reason=" ", approved_by="N-SW-WEB owner")
    with pytest.raises(InvariantError, match="approval"):
        person.change_capacity(ReferralCapacity(24), reason="leadership duties reduced", approved_by="")
    assert person.capacity.hours_per_week == 18 and person.profile_version == "1.0"


def test_capacity_change_bumps_version_and_records_event() -> None:
    person = make_executor(hours=18)
    person.change_capacity(ReferralCapacity(24), reason="leadership duties reduced", approved_by="N-SW-WEB owner")
    assert person.capacity.hours_per_week == 24
    assert person.profile_version == "1.1"
    event = person.events[-1]
    assert event.name == "ExecutorProfileChanged"
    assert event.payload["old"] == 18 and event.payload["new"] == 24 and event.payload["version"] == "1.1"
