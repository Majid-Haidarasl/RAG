"""Registry validation: references, record rules and project status consistency.

The validator never raises; it returns a list of ``Problem`` values so the
check script can print every problem at once. Codes:

``duplicate_id``, ``unknown_node``, ``unknown_document``, ``unknown_issue``,
``unknown_project``, ``missing_evidence``, ``missing_conditions``,
``achievement_open``, ``research_claims_result``, ``research_plan_incomplete``,
``unsolved_needs_issue``, ``unsolved_not_open``, ``unknown_research``,
``status_inconsistent``.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass

from rag_core.projects.domain.model import (
    ClaimState,
    ProjectRegistry,
    ProjectStatus,
    RecordKind,
)

CLOSED_ISSUE_STATUSES = frozenset({"resolved", "closed"})


@dataclass(frozen=True)
class Problem:
    code: str
    ref: str
    message: str

    def __str__(self) -> str:
        return f"{self.code}:{self.ref}"


@dataclass(frozen=True)
class IssueFacts:
    """What the project context needs to know about one registered issue."""

    issue_id: str
    status: str
    risk: int = 0
    blocked_subissues: int = 0

    @property
    def is_open(self) -> bool:
        return self.status not in CLOSED_ISSUE_STATUSES


def health(project_issues: list[IssueFacts], *, risk_threshold: int = 7) -> str:
    """``at_risk`` (an open linked issue with high risk or a blocked sub-issue), ``watch`` or ``on_track``."""
    open_issues = [i for i in project_issues if i.is_open]
    if any(i.risk >= risk_threshold or i.blocked_subissues > 0 for i in open_issues):
        return "at_risk"
    if open_issues:
        return "watch"
    return "on_track"


class RegistryValidator:
    def __init__(
        self,
        nodes: Collection[str],
        documents: Collection[str],
        issues: Mapping[str, IssueFacts],
        *,
        risk_threshold: int = 7,
    ) -> None:
        self.nodes = set(nodes)
        self.documents = set(documents)
        self.issues = dict(issues)
        self.risk_threshold = risk_threshold

    def validate(self, registry: ProjectRegistry) -> list[Problem]:
        problems: list[Problem] = []
        problems += self._duplicates(registry)
        project_ids = {p.project_id for p in registry.projects}
        for p in registry.projects:
            problems += self._nodes(p.project_id, p.all_nodes)
            problems += self._documents(p.project_id, p.evidence)
            problems += self._issues(p.project_id, p.issues)
            if not p.evidence:
                problems.append(
                    Problem(
                        "missing_evidence", p.project_id, "a project must cite evidence"
                    )
                )
            computed = health(
                [self.issues[i] for i in p.issues if i in self.issues],
                risk_threshold=self.risk_threshold,
            )
            if (p.status is ProjectStatus.AT_RISK) != (computed == "at_risk"):
                problems.append(
                    Problem(
                        "status_inconsistent",
                        p.project_id,
                        f"registry status {p.status.value}, linked issues say {computed}",
                    )
                )
        record_ids = {r.record_id for r in registry.records}
        for r in registry.records:
            ref = r.record_id
            problems += self._nodes(ref, r.nodes)
            problems += self._documents(ref, r.evidence)
            problems += self._issues(ref, r.issues)
            if r.project and r.project not in project_ids:
                problems.append(
                    Problem(
                        "unknown_project", ref, f"project {r.project} is not registered"
                    )
                )
            if not r.evidence:
                problems.append(
                    Problem("missing_evidence", ref, "every record must cite evidence")
                )
            if r.is_lesson and not r.conditions.strip():
                problems.append(
                    Problem(
                        "missing_conditions",
                        ref,
                        "a lesson must keep its applicability conditions",
                    )
                )
            if r.kind is RecordKind.ACHIEVEMENT and r.state is ClaimState.OPEN:
                problems.append(
                    Problem(
                        "achievement_open",
                        ref,
                        "an achievement is recorded or conditional",
                    )
                )
            if r.kind is RecordKind.RESEARCH:
                problems += self._research(r)
            if r.kind is RecordKind.UNSOLVED_ISSUE:
                if not r.issues:
                    problems.append(
                        Problem(
                            "unsolved_needs_issue",
                            ref,
                            "an unsolved issue links a registered issue",
                        )
                    )
                if r.state is not ClaimState.OPEN:
                    problems.append(
                        Problem(
                            "unsolved_not_open", ref, "an unsolved issue stays open"
                        )
                    )
        for d in registry.scorecard:
            problems += self._documents(d.dimension_id, d.evidence)
            if d.research and d.research not in record_ids:
                problems.append(
                    Problem(
                        "unknown_research",
                        d.dimension_id,
                        f"research record {d.research} not found",
                    )
                )
        return problems

    # -- helpers ---------------------------------------------------------------------
    @staticmethod
    def _duplicates(registry: ProjectRegistry) -> list[Problem]:
        seen: set[str] = set()
        out: list[Problem] = []
        ids = (
            [p.project_id for p in registry.projects]
            + [r.record_id for r in registry.records]
            + [d.dimension_id for d in registry.scorecard]
        )
        for i in ids:
            if i in seen:
                out.append(
                    Problem("duplicate_id", i, "ids must be unique across the registry")
                )
            seen.add(i)
        return out

    def _nodes(self, ref: str, nodes: tuple[str, ...]) -> list[Problem]:
        return [
            Problem("unknown_node", ref, f"node {n} is not in the hierarchy registry")
            for n in nodes
            if n not in self.nodes
        ]

    def _documents(self, ref: str, documents: tuple[str, ...]) -> list[Problem]:
        return [
            Problem(
                "unknown_document",
                ref,
                f"document {d} is not an active corpus document",
            )
            for d in documents
            if d not in self.documents
        ]

    def _issues(self, ref: str, issues: tuple[str, ...]) -> list[Problem]:
        return [
            Problem("unknown_issue", ref, f"issue {i} is not registered")
            for i in issues
            if i not in self.issues
        ]

    @staticmethod
    def _research(r) -> list[Problem]:  # noqa: ANN001
        out: list[Problem] = []
        if r.validated_result or r.state is ClaimState.RECORDED:
            out.append(
                Problem(
                    "research_claims_result",
                    r.record_id,
                    "an open research gap may not claim a validated result",
                )
            )
        if not (r.people and r.nodes and r.risks and r.evidence_needed):
            out.append(
                Problem(
                    "research_plan_incomplete",
                    r.record_id,
                    "a research gap needs people, nodes, risks and the evidence it needs",
                )
            )
        return out
