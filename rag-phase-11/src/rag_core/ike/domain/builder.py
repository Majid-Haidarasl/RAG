"""Build the IKE graph of one issue from its views, referrals and comparisons.

Relations created (all checked against ``RELATION_RULES``):

=================  ==========================  =====================================================
type               source → target             when
=================  ==========================  =====================================================
part_of            sub-issue → issue           every sub-issue
depends_on         sub-issue → sibling         every registry dependency
relates_to         issue → document            documents the issue cites (not its own file id)
relates_to         sub-issue → document        cited (1.0) or retrieved in scope but not cited
can_handle         executor → sub-issue        every recommended executor (confidence = match score)
evidence_for       document → executor         the executor holds a document the item cites
knowledge_lack     sub-issue → document        cited document no recommended executor holds
knowledge_lack     sub-issue → document        cited document outside the owner node's scope
knowledge_lack     sub-issue → gap:…           no lead executor / no in-scope evidence
=================  ==========================  =====================================================

A cited document held only by executors of a sub-issue this one depends on
is still a lack, but with lower confidence and the note "covered through
dependency".
"""

from __future__ import annotations

from rag_core.ike.domain.comparison import IssueKnowledgeComparison
from rag_core.ike.domain.model import IkeGraph, IkeRelation, RelationConfidence, RelationType
from rag_core.ike.domain.views import IssueView, ReferralView, SubItemView
from rag_core.shared_kernel.identifiers import NodeIdentifier

GAP_NO_LEAD = "gap:no-lead-executor"
GAP_NO_EVIDENCE = "gap:no-in-scope-evidence"

NOTE_CITED = "cited by the issue registry"
NOTE_LACK_UNHELD = "no recommended executor holds this knowledge"
NOTE_LACK_DEPENDENCY = "covered through dependency on {dep}"
NOTE_LACK_SCOPE = "cited but outside the owner node's retrieval scope"


def suggestion_confidence(rank: int) -> float:
    """Retrieved-but-not-cited documents: 0.7 at rank 1, minus 0.1 per rank, floor 0.3."""
    return round(max(0.3, 0.7 - 0.1 * (rank - 1)), 2)


def _rel(source: str, target: str, kind: RelationType, confidence: float, note: str) -> IkeRelation:
    return IkeRelation(source, target, kind, RelationConfidence(round(min(1.0, max(0.0, confidence)), 4)), note)


class IkeGraphBuilder:
    def build(
        self,
        issue: IssueView,
        referrals: dict[str, list[ReferralView]],
        comparisons: dict[str, IssueKnowledgeComparison] | None = None,
    ) -> IkeGraph:
        comparisons = comparisons or {}
        graph = IkeGraph(NodeIdentifier(issue.owner_node))
        for doc in dict.fromkeys(issue.related_documents):
            if doc != issue.issue_id:
                graph.add_if_absent(_rel(issue.issue_id, doc, RelationType.RELATES_TO, 1.0, NOTE_CITED))
        for sub in issue.sub_items:
            graph.add_checked(_rel(sub.item_id, issue.issue_id, RelationType.PART_OF, 1.0, "sub-issue of"))
        for sub in issue.sub_items:
            for code in sub.depends_on:
                target = f"{sub.parent_id}/{code}"
                graph.add_checked(_rel(sub.item_id, target, RelationType.DEPENDS_ON, 1.0, "registry dependency"))
        for sub in issue.sub_items:
            self._knowledge(graph, sub, comparisons.get(sub.item_id))
            self._executors(graph, sub, referrals.get(sub.item_id, []))
        for sub in issue.sub_items:
            self._lacks(graph, issue, sub, referrals, comparisons.get(sub.item_id))
        return graph

    def _knowledge(self, graph: IkeGraph, sub: SubItemView, comparison: IssueKnowledgeComparison | None) -> None:
        for doc in dict.fromkeys(sub.related_documents):
            note = NOTE_CITED
            if comparison is not None:
                rank = comparison.rank_of(doc)
                note += f"; retrieved rank {rank}" if rank else "; not retrieved in scope"
            graph.add_if_absent(_rel(sub.item_id, doc, RelationType.RELATES_TO, 1.0, note))
        if comparison is None:
            return
        for doc in comparison.suggested:
            rank = comparison.rank_of(doc) or len(comparison.retrieved)
            graph.add_if_absent(_rel(sub.item_id, doc, RelationType.RELATES_TO, suggestion_confidence(rank),
                                     f"retrieved in scope rank {rank}, not cited ({comparison.mode})"))

    def _executors(self, graph: IkeGraph, sub: SubItemView, refs: list[ReferralView]) -> None:
        cited = set(sub.related_documents)
        for ref in refs:
            graph.add_if_absent(_rel(ref.executor_id, sub.item_id, RelationType.CAN_HANDLE, ref.score,
                                     f"{ref.role} (match score {ref.score:.3f})"))
            for doc in ref.knowledge_documents:
                if doc in cited:
                    graph.add_if_absent(_rel(doc, ref.executor_id, RelationType.EVIDENCE_FOR, 1.0,
                                             "authoritative knowledge in the executor profile (AR-EXE-023)"))

    def _lacks(
        self,
        graph: IkeGraph,
        issue: IssueView,
        sub: SubItemView,
        referrals: dict[str, list[ReferralView]],
        comparison: IssueKnowledgeComparison | None,
    ) -> None:
        refs = referrals.get(sub.item_id, [])
        held = {d for r in refs for d in r.knowledge_documents}
        for doc in dict.fromkeys(sub.related_documents):
            if doc in held:
                continue
            via = None
            for code in sub.depends_on:
                dep_id = f"{sub.parent_id}/{code}"
                if any(doc in r.knowledge_documents for r in referrals.get(dep_id, [])):
                    via = dep_id
                    break
            if via is not None:
                graph.add_if_absent(_rel(sub.item_id, doc, RelationType.KNOWLEDGE_LACK, 0.4,
                                         NOTE_LACK_DEPENDENCY.format(dep=via)))
            else:
                graph.add_if_absent(_rel(sub.item_id, doc, RelationType.KNOWLEDGE_LACK, 0.8, NOTE_LACK_UNHELD))
        if not any(r.role == "lead" for r in refs):
            graph.add_if_absent(_rel(sub.item_id, GAP_NO_LEAD, RelationType.KNOWLEDGE_LACK, 0.9,
                                     "no lead executor in the owner node matches the item"))
        if comparison is not None:
            for doc in comparison.outside_scope:
                graph.add_if_absent(_rel(sub.item_id, doc, RelationType.KNOWLEDGE_LACK, 0.6, NOTE_LACK_SCOPE))
            if not comparison.evidence:
                graph.add_if_absent(_rel(sub.item_id, GAP_NO_EVIDENCE, RelationType.KNOWLEDGE_LACK, 0.7,
                                         f"no in-scope evidence above the floor ({comparison.mode})"))
