"""Executor registry validation (raw JSON records, before aggregates are built).

Errors block loading; warnings are reported only.

Errors: missing fields, invalid or duplicate ids, id not derived from the
canonical name, unknown or retired home node, home node not an execution
team / unit (layer 3), unknown knowledge document, capacity out of range,
no expertise or no allowed referral domain.
Warnings: unpublished capacity, a field that looks like pay.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rag_core.executors.domain.model import MAX_REFERRAL_HOURS, executor_id_for
from rag_core.executors.domain.ports import TeamDirectory
from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.identifiers import ExecutorId

REQUIRED = ("id", "name_en", "home_node", "specialty", "allowed_referral_domains", "expertise", "knowledge_documents")
EXECUTION_LAYER = 3
_PAY_KEYS = ("pay", "salary", "compensation", "pay_mtoman")


@dataclass(frozen=True)
class ExecutorFinding:
    executor_id: str
    rule: str
    message: str

    def __str__(self) -> str:
        return f"{self.executor_id}: [{self.rule}] {self.message}"


@dataclass
class ExecutorValidationReport:
    errors: list[ExecutorFinding] = field(default_factory=list)
    warnings: list[ExecutorFinding] = field(default_factory=list)
    checked: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors


class ExecutorRegistryValidator:
    def __init__(self, directory: TeamDirectory, known_documents: set[str]) -> None:
        self.directory = directory
        self.known_documents = known_documents

    def validate(self, records: list[dict[str, Any]]) -> ExecutorValidationReport:
        report = ExecutorValidationReport()
        seen: set[str] = set()
        for rec in records:
            report.checked += 1
            ident = str(rec.get("id", "?"))
            err = lambda rule, msg: report.errors.append(ExecutorFinding(ident, rule, msg))  # noqa: E731
            warn = lambda rule, msg: report.warnings.append(ExecutorFinding(ident, rule, msg))  # noqa: E731
            missing = [k for k in REQUIRED if not rec.get(k)]
            if missing:
                err("required", "missing " + ", ".join(missing))
                continue
            try:
                ExecutorId(ident)
            except InvariantError as exc:
                err("id", str(exc))
                continue
            if ident in seen:
                err("unique", "duplicate executor id")
            seen.add(ident)
            try:
                expected = str(executor_id_for(rec["name_en"]))
            except InvariantError:
                expected = "?"
            if expected != ident:
                err("id_from_name", f"id should be {expected} for {rec['name_en']!r}")
            node = str(rec["home_node"])
            if not self.directory.exists(node):
                err("home_node", f"unknown or retired node {node}")
            else:
                layer = self.directory.team(node).layer
                if layer != EXECUTION_LAYER:
                    err("home_node_layer", f"{node} is on layer {layer}; executors belong to execution teams (layer 3)")
            for doc in rec["knowledge_documents"]:
                if str(doc).upper() not in self.known_documents:
                    err("knowledge_document", f"unknown document {doc}")
            if len(set(rec["knowledge_documents"])) != len(rec["knowledge_documents"]):
                err("knowledge_document", "duplicate knowledge document")
            hours = rec.get("capacity_hours_per_week")
            if hours is None:
                warn("capacity", "no fixed hours published (allocated through unit planning)")
            elif not isinstance(hours, int) or hours < 0 or hours > MAX_REFERRAL_HOURS:
                err("capacity", f"capacity_hours_per_week must be 0..{MAX_REFERRAL_HOURS} or null, got {hours!r}")
            for key in rec:
                if key.lower() in _PAY_KEYS:
                    warn("confidential", f"field {key!r} looks like pay; pay is not part of the executor registry")
        return report
