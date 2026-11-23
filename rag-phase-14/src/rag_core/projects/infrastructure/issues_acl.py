"""Anti-corruption layer: Phase 7 ``Issue`` aggregates -> ``IssueFacts`` for project tracking."""

from __future__ import annotations

from collections.abc import Iterable

from rag_core.issues.domain.model import Issue
from rag_core.projects.domain.validation import IssueFacts


def issue_facts(issues: Iterable[Issue]) -> dict[str, IssueFacts]:
    out: dict[str, IssueFacts] = {}
    for issue in issues:
        blocked = sum(1 for s in issue.subissues if s.status.value == "blocked")
        out[str(issue.identifier)] = IssueFacts(str(issue.identifier), issue.status.value, int(issue.risk), blocked)
    return out
