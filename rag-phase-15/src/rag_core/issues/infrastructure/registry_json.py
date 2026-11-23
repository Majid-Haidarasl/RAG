"""JSON adapter: data/issues/*.json → Issue aggregates (restore, no transitions replayed)."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from rag_core.issues.domain.model import (
    ContractRef,
    Issue,
    IssueCategory,
    Priority,
    ProgressPercentage,
    Severity,
    SubIssue,
)
from rag_core.issues.domain.status import IssueStatus, Resolution
from rag_core.shared_kernel.identifiers import DocumentId, IssueId, NodeIdentifier

REGISTRY_FILE = "issue-registry.json"
SAMPLES_FILE = "new-issue-samples.json"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _d(value: Any) -> date | None:
    return date.fromisoformat(value) if value else None


def subissue_from_record(rec: dict[str, Any]) -> SubIssue:
    resolution = rec.get("resolution")
    return SubIssue(
        identifier=IssueId(rec["id"]),
        title=rec.get("title_en") or rec["title"],
        status=IssueStatus(rec.get("status", "open")),
        position=int(rec["position"]),
        explicit_progress=ProgressPercentage(Decimal(rec["progress_percent"])) if rec.get("progress_percent") is not None else None,
        owner_node=NodeIdentifier(rec["owner_node"]),
        supporting_nodes=tuple(NodeIdentifier(n) for n in rec.get("supporting_nodes", [])),
        related_documents=tuple(DocumentId(d) for d in rec.get("related_documents", [])),
        depends_on=tuple(rec.get("depends_on", [])),
        scope=rec.get("scope", ""),
        title_fa=rec.get("title_fa", ""),
        executors=tuple(rec.get("executors", [])),
        acceptance_output=rec.get("acceptance_output", ""),
        reserved_decision=bool(rec.get("reserved_decision", False)),
        resolution=Resolution(resolution) if resolution else None,
    )


def issue_from_record(rec: dict[str, Any]) -> Issue:
    """Restore an aggregate from storage; invariants of construction apply."""
    resolution = rec.get("resolution")
    issue = Issue(
        identifier=IssueId(rec["id"]),
        title=rec.get("title_en") or rec["title"],
        owning_node=NodeIdentifier(rec["owner_node"]),
        status=IssueStatus(rec.get("status", "open")),
        explicit_progress=ProgressPercentage(Decimal(rec["progress_percent"])) if rec.get("progress_percent") is not None else None,
        urgency=int(rec.get("urgency", 0)),
        risk=int(rec.get("risk", 0)),
        dependents=int(rec.get("dependents", 0)),
        description=rec.get("description_en") or rec.get("description", ""),
        title_fa=rec.get("title_fa", ""),
        description_fa=rec.get("description_fa", ""),
        reporter_node=NodeIdentifier(rec["reporter_node"]) if rec.get("reporter_node") else None,
        affected_nodes=tuple(NodeIdentifier(n) for n in rec.get("affected_nodes", [])),
        related_documents=tuple(DocumentId(d) for d in rec.get("related_documents", [])),
        contract_ref=ContractRef(rec["contract_ref"]) if rec.get("contract_ref") else None,
        customer=rec.get("customer", ""),
        category=IssueCategory(rec.get("category", "software")),
        severity=Severity(rec.get("severity", "medium")),
        priority_level=Priority(rec.get("priority", "P3")),
        opened_on=_d(rec.get("opened_on")),
        due_on=_d(rec.get("due_on")),
        tags=tuple(rec.get("tags", [])),
        reserved_decision=bool(rec.get("reserved_decision", False)),
        decision_amount_mtoman=rec.get("decision_amount_mtoman"),
        resolution=Resolution(resolution) if resolution else None,
        duplicate_of=IssueId(rec["duplicate_of"]) if rec.get("duplicate_of") else None,
        related_issues=tuple(IssueId(r) for r in rec.get("related_issues", [])),
    )
    for sub in sorted(rec.get("sub_issues", []), key=lambda s: s.get("position", 0)):
        issue.subissues.append(subissue_from_record(sub))
    cycle = issue.dependency_cycle()
    if cycle:
        from rag_core.shared_kernel.errors import InvariantError

        raise InvariantError(f"sub-issue dependency cycle {' -> '.join(cycle)}")
    return issue


def issue_from_sample(rec: dict[str, Any]) -> Issue:
    """A new incoming issue (not yet registered)."""
    data = dict(rec)
    data.setdefault("status", "open")
    data.setdefault("category", data.get("category") or "software")
    data["sub_issues"] = []
    for key in ("expected_label", "expected_best", "language"):
        data.pop(key, None)
    return issue_from_record(data)


class JsonIssueRegistry:
    def __init__(self, directory: Path) -> None:
        self.dir = Path(directory)

    def records(self) -> list[dict[str, Any]]:
        return list(read_json(self.dir / REGISTRY_FILE)["issues"])

    def samples(self) -> list[dict[str, Any]]:
        path = self.dir / SAMPLES_FILE
        return list(read_json(path)["samples"]) if path.exists() else []

    def load(self, records: list[dict[str, Any]] | None = None) -> list[Issue]:
        return [issue_from_record(r) for r in (records if records is not None else self.records())]
