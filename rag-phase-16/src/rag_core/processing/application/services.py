"""CycleProcessor: run one processing cycle bottom-up over a plan.

For each step (leaves first): collect the *accepted* packages that the
node's children sent in this cycle, ask the transfer port for the node's own
package, store it (latest revision + history) and forward it to the parent
only if it was accepted. A failing node is reported and does not stop the
cycle; its parent then notes that a child package is missing.
Running the same cycle again with the same knowledge stores nothing new.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rag_core.processing.domain.cycle import CycleReport, ProcessingCycle, StepOutcome, StepResult
from rag_core.processing.domain.plan import ProcessingPlan
from rag_core.processing.domain.ports import NodeTransferPort, PackageStorePort


@dataclass
class CycleRun:
    report: CycleReport
    packages: dict[str, Any] = field(default_factory=dict)  # source node -> package

    def accepted_packages(self) -> list[Any]:
        return [p for p in self.packages.values() if p.accepted]


class CycleProcessor:
    def __init__(self, transfer: NodeTransferPort) -> None:
        self.transfer = transfer

    def run(self, cycle: ProcessingCycle, plan: ProcessingPlan, *, store: PackageStorePort | None = None) -> CycleRun:
        report = CycleReport(cycle.cycle_id, skipped=[(s.node_id, s.reason) for s in plan.skipped])
        run = CycleRun(report)
        inbox: dict[str, list[Any]] = {}
        for step in plan.steps:
            received = list(inbox.get(step.source_node, []))
            expected = len(plan.children_of(step.source_node))
            try:
                package = self.transfer.transfer(cycle.cycle_id, step, received, expected)
            except Exception as exc:  # noqa: BLE001 - one failing node must not stop the cycle
                report.steps.append(StepResult(step.order, step.source_node, step.target_node, step.target_layer,
                                               StepOutcome.FAILED, received=len(received),
                                               expected_children=expected, reason=f"{type(exc).__name__}: {exc}"))
                continue
            action, revision = "", None
            if store is not None:
                outcome = store.save(package)
                action, revision = outcome.action, outcome.revision
            run.packages[step.source_node] = package
            if package.accepted:
                inbox.setdefault(step.target_node, []).append(package)
            report.steps.append(StepResult(step.order, step.source_node, step.target_node, step.target_layer,
                                           StepOutcome.BUILT, status=package.status,
                                           detail_level=package.detail_level, store_action=action,
                                           revision=revision, received=len(received), expected_children=expected))
        return run
