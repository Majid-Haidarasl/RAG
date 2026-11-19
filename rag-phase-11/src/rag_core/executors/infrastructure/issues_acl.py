"""Anti-corruption layer: Phase 7 issues → executors ``ReferralRequest``.

The only module of the executors context that imports ``issues``. A
sub-issue becomes one request (owner node, supporting nodes, related
documents, English title + scope + acceptance output as matching text).
An issue without sub-issues becomes one request for the whole issue
(owner node, affected nodes as supporting nodes).
"""

from __future__ import annotations

from rag_core.executors.domain.matching import ReferralRequest
from rag_core.issues.domain.model import Issue, SubIssue


def request_for_subissue(sub: SubIssue) -> ReferralRequest:
    text = " ".join(p for p in (sub.title, sub.scope, sub.acceptance_output) if p)
    return ReferralRequest(
        item_id=str(sub.identifier),
        owner_node=str(sub.owner_node) if sub.owner_node else "",
        supporting_nodes=tuple(str(n) for n in sub.supporting_nodes),
        related_documents=tuple(str(d) for d in sub.related_documents),
        text=text,
        reserved_decision=sub.reserved_decision,
        named_executors=tuple(sub.executors),
    )


def request_for_issue(issue: Issue) -> ReferralRequest:
    return ReferralRequest(
        item_id=str(issue.identifier),
        owner_node=str(issue.owning_node),
        supporting_nodes=tuple(str(n) for n in issue.affected_nodes if n != issue.owning_node),
        related_documents=tuple(str(d) for d in issue.related_documents if str(d) != str(issue.identifier)),
        text=" ".join(p for p in (issue.title, issue.description) if p),
        reserved_decision=issue.is_reserved_decision,
    )


def referral_requests(issue: Issue) -> list[ReferralRequest]:
    """One request per sub-issue (in position order), or one for a flat issue."""
    if issue.subissues:
        return [request_for_subissue(s) for s in sorted(issue.subissues, key=lambda s: s.position)]
    return [request_for_issue(issue)]
