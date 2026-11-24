"""Anti-corruption layer: Phase 7 issues, Phase 12 ranking and gaps -> RFP generator views."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from rag_core.rfp.domain.generator import GapView, ItemView, KeyIssueView


def key_issue_views(ranked: Iterable[Any], issues: Iterable[Any]) -> list[KeyIssueView]:
    """``ranked``: Phase 12 ``PriorityScore`` rows (only ``key`` rows are used)."""
    by_id = {str(i.identifier): i for i in issues}
    out: list[KeyIssueView] = []
    for s in ranked:
        if not getattr(s, "key", False):
            continue
        issue = by_id.get(s.issue_id)
        category = issue.category.value if issue is not None else ""
        status = issue.status.value if issue is not None else ""
        out.append(
            KeyIssueView(
                s.issue_id,
                s.title_en,
                s.title_fa,
                category,
                status,
                int(s.rank),
                float(s.score),
                tuple(s.top_factors()),
            )
        )
    return out


def item_views(issues: Iterable[Any]) -> dict[str, ItemView]:
    out: dict[str, ItemView] = {}
    for issue in issues:
        for sub in issue.subissues:
            owner = str(sub.owner_node or issue.owning_node)
            out[str(sub.identifier)] = ItemView(
                str(sub.identifier),
                sub.status.value,
                owner,
                sub.title,
                sub.title_fa or "",
            )
    return out


def gap_views(gaps: Iterable[Any]) -> list[GapView]:
    """``gaps``: Phase 12 ``Gap`` rows; only gaps tied to an issue are used."""
    return [
        GapView(
            g.gap_id, g.subject, g.severity.value, g.title_en, g.title_fa, g.issue_id
        )
        for g in gaps
        if g.issue_id
    ]


def executor_nodes(executors: Iterable[Any]) -> dict[str, str]:
    """Phase 9 ``Executor`` records -> executor id -> home node id."""
    return {str(e.identifier): str(e.home_node) for e in executors}
