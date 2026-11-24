"""Anti-corruption layer: hierarchy, knowledge, issues, executors and IKE → ``NodeKnowledge``.

The only transfer module that imports the other contexts' aggregates. It
copies plain values out of them:

* hierarchy (Phase 6): node names and layers, documents each node owns;
* knowledge lifecycle (Phase 5, via the chunk records): active version of each
  document — only active documents are cited;
* issues (Phase 7): issues a node owns, sub-issues it owns or supports;
* executors (Phase 9): people at the node and their referral capacity;
* IKE (Phase 9): lead / collaborators and knowledge lacks per sub-issue.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace

from rag_core.executors.domain.model import Executor
from rag_core.hierarchy.domain.model import Organization
from rag_core.hierarchy.domain.ownership import DocumentOwnership, OwnershipRole
from rag_core.issues.domain.model import Issue
from rag_core.transfer.domain.items import (
    DocumentRef,
    ExecutorRef,
    IssueContext,
    ItemRole,
    NodeKnowledge,
    TransferItem,
    rank_items,
)

# item id -> (lead, lead_fa, collaborators, collaborators_fa)
Leads = Mapping[str, tuple[str, str, tuple[str, ...], tuple[str, ...]]]


def document_versions(records: Iterable[object]) -> dict[str, str]:
    """Active version per document from Phase 8 chunk records (Phase 5 lifecycle)."""
    out: dict[str, str] = {}
    for r in records:
        if (
            getattr(r, "version_status", "active") != "active"
            or getattr(r, "status", "active") != "active"
        ):
            continue
        doc = str(getattr(r, "document_id"))
        version = str(getattr(r, "version"))
        current = out.get(doc)
        if current is None or _version_key(version) > _version_key(current):
            out[doc] = version
    return out


def _version_key(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for p in version.split("."):
        parts.append(int(p) if p.isdigit() else 0)
    return tuple(parts)


def issue_context(issue: Issue) -> IssueContext:
    return IssueContext(
        issue_id=str(issue.identifier),
        title_en=issue.title,
        title_fa=issue.title_fa,
        status=issue.status.value,
        priority=issue.priority_level.value,
        progress=int(issue.explicit_progress)
        if issue.explicit_progress is not None
        else None,
        contract_ref=str(issue.contract_ref) if issue.contract_ref else "",
        decision_amount_mtoman=issue.decision_amount_mtoman,
        due_on=issue.due_on.isoformat() if issue.due_on else "",
        risk=issue.risk,
        customer=issue.customer,
    )


def items_for_node(
    node_id: str,
    issues: Iterable[Issue],
    leads: Leads | None = None,
    lacks: Mapping[str, tuple[str, ...]] | None = None,
) -> tuple[TransferItem, ...]:
    leads = leads or {}
    lacks = lacks or {}
    out: list[TransferItem] = []
    for issue in issues:
        ctx = issue_context(issue)
        if issue.subissues:
            for sub in sorted(issue.subissues, key=lambda s: s.position):
                owner = str(sub.owner_node) if sub.owner_node else ""
                supporters = {str(n) for n in sub.supporting_nodes}
                if owner == node_id:
                    role = ItemRole.OWNER
                elif node_id in supporters:
                    role = ItemRole.SUPPORT
                else:
                    continue
                item_id = str(sub.identifier)
                lead, lead_fa, collab, collab_fa = leads.get(item_id, ("", "", (), ()))
                out.append(
                    TransferItem(
                        item_id=item_id,
                        title_en=sub.title,
                        title_fa=sub.title_fa,
                        status=sub.status.value,
                        owner_node=owner or str(issue.owning_node),
                        origin_node=node_id,
                        role=role,
                        issue=ctx,
                        lead=lead,
                        lead_fa=lead_fa,
                        collaborators=tuple(collab),
                        collaborators_fa=tuple(collab_fa),
                        depends_on=tuple(
                            f"{issue.identifier}/{code}" for code in sub.depends_on
                        ),
                        documents=tuple(str(d) for d in sub.related_documents),
                        gaps=tuple(lacks.get(item_id, ())),
                        acceptance_output=sub.acceptance_output,
                        reserved_decision=sub.reserved_decision,
                        priority=issue.priority_level.value,
                        risk=issue.risk,
                    )
                )
        elif str(issue.owning_node) == node_id:
            item_id = str(issue.identifier)
            lead, lead_fa, collab, collab_fa = leads.get(item_id, ("", "", (), ()))
            out.append(
                TransferItem(
                    item_id=item_id,
                    title_en=issue.title,
                    title_fa=issue.title_fa,
                    status=issue.status.value,
                    owner_node=node_id,
                    origin_node=node_id,
                    role=ItemRole.OWNER,
                    issue=ctx,
                    lead=lead,
                    lead_fa=lead_fa,
                    collaborators=tuple(collab),
                    collaborators_fa=tuple(collab_fa),
                    documents=tuple(str(d) for d in issue.related_documents),
                    gaps=tuple(lacks.get(item_id, ())),
                    reserved_decision=issue.reserved_decision,
                    priority=issue.priority_level.value,
                    risk=issue.risk,
                )
            )
    return tuple(rank_items(out))


def executors_for_node(
    node_id: str, executors: Iterable[Executor]
) -> tuple[ExecutorRef, ...]:
    refs = [
        ExecutorRef(
            str(e.identifier), e.display_name, e.name_fa, e.capacity.hours_per_week
        )
        for e in executors
        if str(e.home_node) == node_id
    ]
    return tuple(sorted(refs, key=lambda r: r.name_en))


def owned_documents(
    node_id: str, ownership: DocumentOwnership, versions: Mapping[str, str]
) -> tuple[DocumentRef, ...]:
    from rag_core.shared_kernel.identifiers import NodeIdentifier

    docs = ownership.documents_of(NodeIdentifier(node_id), OwnershipRole.OWNER)
    return tuple(
        DocumentRef(str(d), versions[str(d)])
        for d in sorted(docs)
        if str(d) in versions
    )


def build_knowledge(
    org: Organization,
    ownership: DocumentOwnership,
    issues: list[Issue],
    executors: list[Executor],
    versions: Mapping[str, str],
    leads: Leads | None = None,
    lacks: Mapping[str, tuple[str, ...]] | None = None,
) -> dict[str, NodeKnowledge]:
    out: dict[str, NodeKnowledge] = {}
    for node in org.all_nodes():
        node_id = str(node.identifier)
        out[node_id] = NodeKnowledge(
            node_id=node_id,
            layer=node.layer.value,
            name_en=node.name_en,
            name_fa=node.name_fa,
            documents=owned_documents(node_id, ownership, versions),
            items=items_for_node(node_id, issues, leads, lacks),
            executors=executors_for_node(node_id, executors),
        )
    return out


def layer_rules_from_registry(org: Organization) -> dict[int, tuple[str, int | None]]:
    """Layer registry → (default detail level received, max package words) for the rule check."""
    return {
        i: (layer.default_detail_level, layer.max_package_words)
        for i, layer in org.layers.items()
    }


def sender_level_mismatches(
    org: Organization, senders: Iterable[str], level_of_layer: Mapping[int, str]
) -> list[str]:
    """Each sender's ``transfer_detail_level_to_parent`` must equal the receiving layer's level."""
    from rag_core.shared_kernel.identifiers import NodeIdentifier

    problems: list[str] = []
    for node_id in senders:
        node = org.get(NodeIdentifier(node_id))
        if node.parent_id is None:
            continue
        parent = org.get(node.parent_id)
        expected = level_of_layer.get(parent.layer.value, "")
        if (
            node.transfer_detail_level_to_parent
            and node.transfer_detail_level_to_parent != expected
        ):
            problems.append(
                f"{node_id}: registry {node.transfer_detail_level_to_parent} != {expected}"
            )
    return problems


def with_item_status(
    knowledge: Mapping[str, NodeKnowledge], node_id: str, item_id: str, status: str
) -> dict[str, NodeKnowledge]:
    """Copy of the knowledge where one node reports a new status for one item (update simulation)."""
    out = dict(knowledge)
    k = out[node_id]
    items = tuple(
        replace(i, status=status) if i.item_id == item_id else i for i in k.items
    )
    out[node_id] = replace(k, items=items)
    return out
