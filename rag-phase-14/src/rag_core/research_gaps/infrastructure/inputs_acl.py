"""Anti-corruption layer: issues (Phase 7), IKE digest (Phase 9) and project tracking -> ``GapInputs``."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date

from rag_core.issues.domain.model import Issue
from rag_core.projects.domain.model import ProjectRegistry
from rag_core.research_gaps.domain.model import (
    DimensionView,
    GapInputs,
    IssueStateView,
    RecordView,
    SubIssueView,
)

# item id -> (lead executor id or name, lacks targets)
IkeItems = Mapping[str, tuple[str, tuple[str, ...]]]


def ike_items(digest: object | None) -> dict[str, tuple[str, tuple[str, ...]]]:
    """Phase 9 ``IssueDigest`` -> {sub-issue id: (lead, unique lack targets)}."""
    out: dict[str, tuple[str, tuple[str, ...]]] = {}
    if digest is None:
        return out
    for it in getattr(digest, "items", ()):
        targets = tuple(dict.fromkeys(str(t) for t, _ in getattr(it, "lacks", ())))
        out[str(it.item_id)] = (str(it.lead or ""), targets)
    return out


def issue_views(issues: Iterable[Issue]) -> tuple[IssueStateView, ...]:
    return tuple(IssueStateView(str(i.identifier), i.status.value, i.title, i.title_fa) for i in issues)


def subissue_views(issues: Iterable[Issue], ike: IkeItems | None = None) -> tuple[SubIssueView, ...]:
    ike = ike or {}
    out: list[SubIssueView] = []
    for issue in issues:
        parent = str(issue.identifier)
        for sub in sorted(issue.subissues, key=lambda s: s.position):
            item_id = str(sub.identifier)
            lead, lacks = ike.get(item_id, ("", ()))
            out.append(SubIssueView(
                item_id=item_id, issue_id=parent, title_en=sub.title, title_fa=sub.title_fa, status=sub.status.value,
                owner_node=str(sub.owner_node) if sub.owner_node else "", executors=tuple(sub.executors), lead=lead,
                lacks=tuple(lacks), depends_on=tuple(f"{parent}/{code}" for code in sub.depends_on),
                documents=tuple(str(d) for d in sub.related_documents),
            ))
    return tuple(out)


def record_views(registry: ProjectRegistry) -> tuple[RecordView, ...]:
    return tuple(RecordView(r.record_id, r.kind.value, r.state.value, r.title_en, r.title_fa, r.issues, r.nodes,
                            r.evidence, r.people, r.validated_result) for r in registry.records)


def dimension_views(registry: ProjectRegistry) -> tuple[DimensionView, ...]:
    return tuple(DimensionView(d.dimension_id, d.name_en, d.name_fa, d.state.value, d.evidence, d.research)
                 for d in registry.scorecard)


def build_inputs(registry: ProjectRegistry, issues: list[Issue], ike: IkeItems | None = None,
                 as_of: date | None = None) -> GapInputs:
    return GapInputs(records=record_views(registry), subissues=subissue_views(issues, ike),
                     issues=issue_views(issues), scorecard=dimension_views(registry), as_of=as_of)
