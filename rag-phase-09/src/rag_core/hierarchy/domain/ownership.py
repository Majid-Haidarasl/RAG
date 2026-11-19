"""Document → node ownership links and knowledge reassignment on retirement."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.events import DomainEvent
from rag_core.shared_kernel.identifiers import DocumentId, NodeIdentifier


class OwnershipRole(StrEnum):
    OWNER = "owner"  # accountable owner, exactly one per document
    CO_OWNER = "co_owner"  # officially shares ownership (catalog additional nodes)
    DESCRIBED_IN = "described_in"  # the document describes the node (registry source_docs)


@dataclass(frozen=True)
class OwnershipLink:
    document_id: DocumentId
    node_id: NodeIdentifier
    role: OwnershipRole
    source: str = ""


@dataclass(frozen=True)
class Reassignment:
    document_id: DocumentId
    role: OwnershipRole
    from_node: NodeIdentifier
    to_node: NodeIdentifier


@dataclass
class DocumentOwnership:
    """All ownership links. Invariant: exactly one OWNER per document."""

    links: list[OwnershipLink] = field(default_factory=list)
    events: list[DomainEvent] = field(default_factory=list)

    def add(self, link: OwnershipLink) -> None:
        if any(l.document_id == link.document_id and l.node_id == link.node_id for l in self.links):
            raise InvariantError(f"duplicate link {link.document_id} → {link.node_id}")
        if link.role is OwnershipRole.OWNER and self.owner_of(link.document_id) is not None:
            raise InvariantError(f"{link.document_id} already has an owner")
        self.links.append(link)

    def documents(self) -> list[DocumentId]:
        return sorted({l.document_id for l in self.links}, key=lambda d: d.value)

    def owner_of(self, document_id: DocumentId) -> NodeIdentifier | None:
        for link in self.links:
            if link.document_id == document_id and link.role is OwnershipRole.OWNER:
                return link.node_id
        return None

    def co_owners_of(self, document_id: DocumentId) -> tuple[NodeIdentifier, ...]:
        return tuple(
            l.node_id for l in self.links if l.document_id == document_id and l.role is OwnershipRole.CO_OWNER
        )

    def readers_of(self, document_id: DocumentId) -> tuple[NodeIdentifier, ...]:
        return tuple(
            l.node_id for l in self.links if l.document_id == document_id and l.role is OwnershipRole.DESCRIBED_IN
        )

    def documents_of(self, node_id: NodeIdentifier, *roles: OwnershipRole) -> list[DocumentId]:
        wanted = set(roles) or {OwnershipRole.OWNER, OwnershipRole.CO_OWNER}
        return sorted(
            {l.document_id for l in self.links if l.node_id == node_id and l.role in wanted}, key=lambda d: d.value
        )

    def unowned(self, expected: list[DocumentId]) -> list[DocumentId]:
        return [d for d in expected if self.owner_of(d) is None]

    def reassign(self, from_node: NodeIdentifier, to_node: NodeIdentifier) -> list[Reassignment]:
        """Move OWNER/CO_OWNER links of a retired node to its successor.

        A co-ownership becomes redundant (and is dropped) when the successor is
        already linked to the document; DESCRIBED_IN links stay as history.
        """
        if from_node == to_node:
            raise InvariantError("cannot reassign knowledge to the same node")
        changes: list[Reassignment] = []
        kept: list[OwnershipLink] = []
        moving = [l for l in self.links if l.node_id == from_node and l.role is not OwnershipRole.DESCRIBED_IN]
        for link in self.links:
            if link not in moving:
                kept.append(link)
        for link in moving:
            existing = [k for k in kept if k.document_id == link.document_id and k.node_id == to_node]
            if link.role is OwnershipRole.OWNER:
                kept = [k for k in kept if k not in existing]  # successor becomes owner
                kept.append(OwnershipLink(link.document_id, to_node, OwnershipRole.OWNER, f"reassigned from {from_node}"))
            elif not existing:
                kept.append(OwnershipLink(link.document_id, to_node, link.role, f"reassigned from {from_node}"))
            changes.append(Reassignment(link.document_id, link.role, from_node, to_node))
        self.links = kept
        if changes:
            self.events.append(
                DomainEvent(
                    "KnowledgeReassigned",
                    {
                        "from": str(from_node),
                        "to": str(to_node),
                        "documents": sorted({str(c.document_id) for c in changes}),
                    },
                )
            )
        return changes
