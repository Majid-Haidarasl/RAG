"""Anti-corruption layer: Phase 7 issues → IKE ``IssueView`` / ``SubItemView``.

The only module of the IKE context that imports ``issues``.
"""

from __future__ import annotations

from rag_core.ike.domain.views import IssueView, SubItemView
from rag_core.issues.domain.model import Issue, SubIssue


def sub_item_view(sub: SubIssue) -> SubItemView:
    return SubItemView(
        item_id=str(sub.identifier),
        code=sub.code,
        title=sub.title,
        owner_node=str(sub.owner_node) if sub.owner_node else "",
        status=sub.status.value,
        title_fa=sub.title_fa,
        scope=sub.scope,
        supporting_nodes=tuple(str(n) for n in sub.supporting_nodes),
        related_documents=tuple(str(d) for d in sub.related_documents),
        depends_on=tuple(sub.depends_on),
        acceptance_output=sub.acceptance_output,
        reserved_decision=sub.reserved_decision,
    )


def recorded_progress(issue: Issue) -> int:
    """Recorded physical progress (AR-ISS-024: 62%) when present, else the Phase 7 roll-up."""
    if issue.explicit_progress is not None:
        return int(issue.explicit_progress)
    return int(issue.progress())


def issue_view(issue: Issue) -> IssueView:
    return IssueView(
        issue_id=str(issue.identifier),
        title=issue.title,
        owner_node=str(issue.owning_node),
        status=issue.status.value,
        progress_percent=recorded_progress(issue),
        title_fa=issue.title_fa,
        customer=issue.customer,
        contract_ref=str(issue.contract_ref) if issue.contract_ref else "",
        related_documents=tuple(str(d) for d in issue.related_documents),
        reserved_decision=issue.is_reserved_decision,
        sub_items=tuple(sub_item_view(s) for s in sorted(issue.subissues, key=lambda s: s.position)),
    )
