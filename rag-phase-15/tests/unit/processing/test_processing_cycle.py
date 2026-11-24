"""ProcessingCycle value object and the cycle report."""

import pytest

from rag_core.processing.domain.cycle import (
    CycleReport,
    ProcessingCycle,
    StepOutcome,
    StepResult,
)
from rag_core.shared_kernel.errors import InvariantError

pytestmark = [pytest.mark.processing]


def test_quarter_cycle_parts() -> None:
    c = ProcessingCycle("1403-Q2", "1403-06-31", "quarter close")
    assert (c.cycle_id, c.year, c.period, str(c)) == ("1403-Q2", 1403, "Q2", "1403-Q2")


def test_month_cycle_and_normalization() -> None:
    assert ProcessingCycle("1403-m06").cycle_id == "1403-M06"
    assert ProcessingCycle("۱۴۰۳-Q1").cycle_id == "1403-Q1"


@pytest.mark.parametrize("bad", ["1403-Q5", "1403-M13", "1403", "Q2-1403", ""])
def test_invalid_cycle_ids_are_rejected(bad: str) -> None:
    with pytest.raises(InvariantError):
        ProcessingCycle(bad)


def _step(
    order: int,
    node: str,
    layer: int,
    outcome: StepOutcome,
    status: str = "",
    action: str = "",
) -> StepResult:
    return StepResult(
        order, node, "N-X", layer, outcome, status=status, store_action=action
    )


def test_report_counts_and_layers() -> None:
    report = CycleReport("1403-Q2", skipped=[("N-BRD", "root")])
    report.steps += [
        _step(1, "N-A", 2, StepOutcome.BUILT, "accepted", "inserted"),
        _step(2, "N-B", 2, StepOutcome.BUILT, "rejected", "unchanged"),
        _step(3, "N-C", 1, StepOutcome.FAILED),
    ]
    counts = report.counts()
    assert counts == {
        "steps": 3,
        "built": 2,
        "failed": 1,
        "accepted": 1,
        "rejected": 1,
        "inserted": 1,
        "unchanged": 1,
        "updated": 0,
        "skipped": 1,
    }
    assert report.by_layer() == {1: 1, 2: 2}


def test_report_to_dict_is_plain() -> None:
    report = CycleReport("1403-Q2", skipped=[("N-LIB", "repository")])
    report.steps.append(_step(1, "N-A", 2, StepOutcome.BUILT, "accepted", "inserted"))
    data = report.to_dict()
    assert data["steps"][0]["outcome"] == "built"
    assert data["skipped"] == [{"node": "N-LIB", "reason": "repository"}]
    assert data["counts"]["built"] == 1
