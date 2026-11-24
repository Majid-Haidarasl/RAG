"""Phase 12 next action: the sub-issue that unblocks the most others."""

import pytest

from rag_core.prioritization.domain.unblocking import (
    NextAction,
    SubTask,
    dependents_of,
    next_actions,
)

pytestmark = [pytest.mark.prioritization]

HW = "AR-ISS-024/HW"
WIN = "AR-ISS-024/WIN"
WEB = "AR-ISS-024/WEB"
LEG = "AR-ISS-024/LEG"


def case() -> list[SubTask]:
    return [
        SubTask(HW, "in_progress", 1),
        SubTask(WIN, "blocked", 2, (HW,)),
        SubTask(WEB, "in_progress", 3),
        SubTask(LEG, "blocked", 4, (HW,)),
    ]


def test_dependents_of_the_shipped_case() -> None:
    deps = dependents_of(case())
    assert deps[HW] == (LEG, WIN) and deps[WEB] == () and deps[WIN] == ()


def test_next_action_is_the_hardware_sub_issue() -> None:
    assert next_actions(case()) == [NextAction(HW, (LEG, WIN))]
    assert next_actions(case())[0].to_dict() == {"item_id": HW, "unblocks": [LEG, WIN]}


def test_chains_count_indirect_dependents() -> None:
    tasks = [
        SubTask("A", "open", 1),
        SubTask("B", "blocked", 2, ("A",)),
        SubTask("C", "blocked", 3, ("B",)),
    ]
    assert dependents_of(tasks)["A"] == ("B", "C")


def test_closed_waiters_and_blocked_candidates_are_skipped() -> None:
    tasks = [
        SubTask("A", "resolved", 1),
        SubTask("B", "closed", 2, ("A",)),
        SubTask("C", "blocked", 3),
        SubTask("D", "blocked", 4, ("C",)),
    ]
    assert dependents_of(tasks)["A"] == () and next_actions(tasks) == []


def test_most_unblocking_first_then_position() -> None:
    tasks = [
        SubTask("A", "open", 2),
        SubTask("B", "open", 1),
        SubTask("X", "blocked", 3, ("A",)),
        SubTask("Y", "blocked", 4, ("A", "B")),
        SubTask("Z", "blocked", 5, ("B",)),
        SubTask("W", "blocked", 6, ("A",)),
    ]
    assert [a.item_id for a in next_actions(tasks)] == ["A", "B"]
    tied = [
        SubTask("A", "open", 2),
        SubTask("B", "open", 1),
        SubTask("X", "blocked", 3, ("A",)),
        SubTask("Z", "blocked", 4, ("B",)),
    ]
    assert [a.item_id for a in next_actions(tied)] == ["B", "A"]


def test_cycles_do_not_loop() -> None:
    tasks = [SubTask("A", "open", 1, ("B",)), SubTask("B", "open", 2, ("A",))]
    assert dependents_of(tasks) == {"A": ("B",), "B": ("A",)}
