"""Anti-corruption layer: issues (Phase 7), projects and gaps (Phase 12) -> ``IssueSignal`` / ``SubTask``."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from rag_core.issues.domain.model import Issue
from rag_core.prioritization.domain.model import IssueSignal
from rag_core.prioritization.domain.unblocking import SubTask


def exposure_by_issue(projects: Iterable[object]) -> dict[str, int]:
    """Remaining project value counts as money at stake for the project's primary issue only."""
    out: dict[str, int] = {}
    for p in projects:
        primary = str(getattr(p, "primary_issue", "") or "")
        remaining = getattr(p, "remaining_mtoman", None)
        if primary and remaining is not None:
            out[primary] = max(out.get(primary, 0), int(remaining))
    return out


def issue_signals(issues: Iterable[Issue], gap_counts: Mapping[str, int] | None = None,
                  exposure: Mapping[str, int] | None = None) -> list[IssueSignal]:
    gap_counts = gap_counts or {}
    exposure = exposure or {}
    out: list[IssueSignal] = []
    for i in issues:
        issue_id = str(i.identifier)
        money = max(int(i.decision_amount_mtoman or 0), int(exposure.get(issue_id, 0)))
        out.append(IssueSignal(
            issue_id=issue_id, title_en=i.title, title_fa=i.title_fa, status=i.status.value,
            priority=i.priority_level.value, severity=i.severity.value, urgency=int(i.urgency), risk=int(i.risk),
            dependents=int(i.dependents), exposure_mtoman=money, subissues=len(i.subissues),
            blocked_subissues=sum(1 for s in i.subissues if s.status.value == "blocked"),
            gaps=int(gap_counts.get(issue_id, 0)), affected_nodes=len(i.affected_nodes),
            progress=int(i.explicit_progress) if i.explicit_progress is not None else None,
            duplicate_of=str(i.duplicate_of) if i.duplicate_of else "",
        ))
    return out


def sub_tasks(issues: Iterable[Issue]) -> dict[str, list[SubTask]]:
    out: dict[str, list[SubTask]] = {}
    for i in issues:
        parent = str(i.identifier)
        out[parent] = [SubTask(str(s.identifier), s.status.value, s.position,
                               tuple(f"{parent}/{code}" for code in s.depends_on)) for s in i.subissues]
    return out
