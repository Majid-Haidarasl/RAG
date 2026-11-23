"""Transfer items: ranking, merging, grouping and capacity."""

import pytest

from rag_core.shared_kernel.errors import InvariantError
from rag_core.transfer.domain.items import (
    CapacitySummary,
    ExecutorRef,
    ItemRole,
    NodeKnowledge,
    TransferItem,
    group_items,
    merge_items,
    rank_items,
    single_groups,
)
from tests.fixtures.transfer.samples import closed_item, hw_item, item, mobile_item, win_item

pytestmark = [pytest.mark.transfer, pytest.mark.transfer_pkg]


def test_item_properties() -> None:
    hw = hw_item()
    assert hw.is_open and hw.is_subissue and not hw.is_blocked
    assert hw.parent_id == "AR-ISS-024"
    assert hw.effective_priority == "P1"
    assert not closed_item().is_open


def test_item_requires_id_status_and_nodes() -> None:
    with pytest.raises(InvariantError):
        item("", "N-HW-REP")
    with pytest.raises(InvariantError):
        item("AR-ISS-031", "N-SW-MOB", status=" ")
    with pytest.raises(InvariantError):
        item("AR-ISS-031", "N-SW-MOB", owner_node="")


def test_rank_puts_open_blocked_and_reserved_first() -> None:
    reserved = item("AR-ISS-024/LEG", "N-ADM-LEG", reserved_decision=True, risk=9)
    ranked = rank_items([closed_item(), mobile_item(), hw_item(), win_item(), reserved])
    assert [i.item_id for i in ranked] == ["AR-ISS-024/LEG", "AR-ISS-024/WIN", "AR-ISS-024/HW", "AR-ISS-031",
                                           "AR-ISS-034"]


def test_merge_keeps_owner_copy() -> None:
    support = hw_item(origin="N-HW-ADV", status="blocked")
    owner = hw_item()
    merged = merge_items([support, owner, support])
    assert len(merged) == 1
    assert merged[0].role is ItemRole.OWNER
    assert merged[0].status == "in_progress"


def test_group_items_by_parent_issue() -> None:
    groups = group_items([hw_item(), mobile_item(), win_item()])
    assert [g.group_id for g in groups] == ["AR-ISS-024", "AR-ISS-031"]
    first = groups[0]
    assert first.item_ids == ("AR-ISS-024/WIN", "AR-ISS-024/HW")
    assert first.is_parent and first.blocked_count == 1 and first.open_count == 2
    assert first.owner_nodes == ("N-HW-REP", "N-SW-WIN")
    assert not groups[1].is_parent


def test_single_groups_keep_one_item_each() -> None:
    groups = single_groups([closed_item(), hw_item()])
    assert [g.item_ids for g in groups] == [("AR-ISS-024/HW",), ("AR-ISS-034",)]
    assert groups[1].issue.issue_id == "AR-ISS-034"


def test_item_round_trip_dict() -> None:
    original = win_item()
    assert TransferItem.from_dict(original.to_dict()) == original


def test_capacity_of_and_plus() -> None:
    a = CapacitySummary.of([ExecutorRef("E1", "Saeed Akbari", "سعید اکبری", 14),
                            ExecutorRef("E2", "Farzaneh Javadi", "فرزانه جوادی", None)])
    assert (a.executors, a.published, a.hours_per_week, a.unit_planning) == (2, 1, 14, ("Farzaneh Javadi",))
    b = CapacitySummary.of([ExecutorRef("E3", "Roozbeh Mohseni", "روزبه محسنی", 10)])
    total = a.plus(b)
    assert (total.executors, total.published, total.hours_per_week) == (3, 2, 24)
    assert [p.name_en for p in total.people] == ["Farzaneh Javadi", "Roozbeh Mohseni", "Saeed Akbari"]
    assert CapacitySummary.from_dict(total.to_dict()) == total


def test_node_knowledge_rejects_foreign_items() -> None:
    with pytest.raises(InvariantError):
        NodeKnowledge("N-HW", 2, "Hardware deputy", items=(hw_item(),))
