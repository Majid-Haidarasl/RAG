"""CycleProcessor: accepted packages travel up, failures and rejections stay visible."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from rag_core.processing.application.services import CycleProcessor
from rag_core.processing.domain.cycle import ProcessingCycle, StepOutcome
from rag_core.processing.domain.plan import TreeNode, build_plan

pytestmark = [pytest.mark.processing]

CYCLE = ProcessingCycle("1403-Q2")


@dataclass
class FakePackage:
    source_node: str
    accepted: bool
    status: str
    detail_level: str = "technical_summary"


@dataclass
class FakeTransfer:
    reject: set[str] = field(default_factory=set)
    fail: set[str] = field(default_factory=set)
    calls: list[tuple[str, list[str], int]] = field(default_factory=list)

    def transfer(self, cycle_id, step, received, expected_children):  # noqa: ANN001, ANN201
        self.calls.append(
            (step.source_node, [p.source_node for p in received], expected_children)
        )
        if step.source_node in self.fail:
            raise RuntimeError("boom")
        ok = step.source_node not in self.reject
        return FakePackage(step.source_node, ok, "accepted" if ok else "rejected")


@dataclass
class FakeStore:
    saved: list[str] = field(default_factory=list)

    def save(self, package):  # noqa: ANN001, ANN201
        self.saved.append(package.source_node)

        @dataclass
        class Outcome:
            action: str = "inserted"
            revision: int = 1

        return Outcome()


def plan():  # noqa: ANN201
    return build_plan(
        [
            TreeNode("N-BRD", 0, None),
            TreeNode("N-CEO", 1, "N-BRD"),
            TreeNode("N-HW", 2, "N-CEO"),
            TreeNode("N-HW-REP", 3, "N-HW"),
            TreeNode("N-HW-ADV", 3, "N-HW"),
        ]
    )


def test_children_packages_reach_their_parent() -> None:
    transfer = FakeTransfer()
    run = CycleProcessor(transfer).run(CYCLE, plan())
    assert transfer.calls == [
        ("N-HW-ADV", [], 0),
        ("N-HW-REP", [], 0),
        ("N-HW", ["N-HW-ADV", "N-HW-REP"], 2),
        ("N-CEO", ["N-HW"], 1),
    ]
    assert run.report.counts()["accepted"] == 4
    assert [p.source_node for p in run.accepted_packages()] == [
        "N-HW-ADV",
        "N-HW-REP",
        "N-HW",
        "N-CEO",
    ]


def test_rejected_package_is_not_forwarded() -> None:
    transfer = FakeTransfer(reject={"N-HW-REP"})
    run = CycleProcessor(transfer).run(CYCLE, plan())
    assert transfer.calls[2] == ("N-HW", ["N-HW-ADV"], 2)
    assert run.report.counts()["rejected"] == 1
    assert "N-HW-REP" in run.packages


def test_failing_node_does_not_stop_the_cycle() -> None:
    run = CycleProcessor(FakeTransfer(fail={"N-HW-ADV"})).run(CYCLE, plan())
    failed = [s for s in run.report.steps if s.outcome is StepOutcome.FAILED]
    assert [s.source_node for s in failed] == ["N-HW-ADV"]
    assert "RuntimeError: boom" in failed[0].reason
    assert run.report.counts()["built"] == 3


def test_store_receives_every_built_package() -> None:
    store = FakeStore()
    run = CycleProcessor(FakeTransfer(fail={"N-HW-ADV"})).run(
        CYCLE, plan(), store=store
    )
    assert store.saved == ["N-HW-REP", "N-HW", "N-CEO"]
    assert {
        s.store_action for s in run.report.steps if s.outcome is StepOutcome.BUILT
    } == {"inserted"}


def test_report_lists_skipped_root() -> None:
    run = CycleProcessor(FakeTransfer()).run(CYCLE, plan())
    assert run.report.skipped[0][0] == "N-BRD"
    assert run.report.cycle_id == "1403-Q2"
