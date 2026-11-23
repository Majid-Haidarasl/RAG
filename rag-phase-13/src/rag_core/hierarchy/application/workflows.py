"""Phase 6 use cases: load + validate the registry, node workflows, coverage."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from rag_core.hierarchy.domain.model import Node, Organization
from rag_core.hierarchy.domain.ownership import DocumentOwnership, OwnershipRole, Reassignment
from rag_core.hierarchy.domain.scope import ScopeResolver
from rag_core.hierarchy.domain.validation import RegistryValidator, ValidationReport, normalize_confidentiality
from rag_core.hierarchy.infrastructure.registry_csv import CsvRegistryLoader
from rag_core.shared_kernel.confidentiality import Confidentiality
from rag_core.shared_kernel.identifiers import DocumentId, NodeIdentifier


def catalog_index() -> dict[str, tuple[str, str]]:
    """Document id → (owning node, confidentiality) from the ingestion catalog."""
    from rag_core.ingestion.domain.catalog import CATALOG

    return {k: (v.owning_node, v.confidentiality) for k, v in CATALOG.items()}


@dataclass
class LoadedRegistry:
    organization: Organization | None
    ownership: DocumentOwnership | None
    report: ValidationReport


def load_and_validate(registry_dir: Path, catalog: dict[str, tuple[str, str]] | None = None) -> LoadedRegistry:
    """Validate raw rows first; only a clean registry is turned into the aggregate."""
    catalog = catalog_index() if catalog is None else catalog
    loader = CsvRegistryLoader(registry_dir)
    rows = loader.rows()
    report = RegistryValidator(catalog).validate(rows.layers, rows.nodes, rows.doc_map)
    if not report.ok:
        return LoadedRegistry(None, None, report)
    return LoadedRegistry(loader.build_organization(rows), loader.build_ownership(rows), report)


@dataclass
class HierarchyWorkflowService:
    organization: Organization
    ownership: DocumentOwnership
    reassignments: list[Reassignment] = field(default_factory=list)

    def add_node(self, node: Node) -> Node:
        return self.organization.add_node(node)

    def move_node(self, node_id: NodeIdentifier, new_parent: NodeIdentifier) -> Node:
        return self.organization.move_node(node_id, new_parent)

    def retire_node(
        self, node_id: NodeIdentifier, successor: NodeIdentifier | None = None, reason: str = ""
    ) -> list[Reassignment]:
        """Retire a node and hand its owned / co-owned knowledge to the successor."""
        target = self.organization.retire_node(node_id, successor, reason=reason)
        changes = self.ownership.reassign(node_id, target)
        self.reassignments.extend(changes)
        return changes


@dataclass(frozen=True)
class CoverageReport:
    documents_total: int
    documents_mapped: list[str]
    documents_unmapped: list[str]
    nodes_with_owned_docs: list[str]
    leaves_without_owned_docs: list[str]
    links_by_role: dict[str, int]

    def as_dict(self) -> dict[str, object]:
        return {
            "documents_total": self.documents_total,
            "documents_mapped": len(self.documents_mapped),
            "documents_unmapped": self.documents_unmapped,
            "nodes_with_owned_docs": self.nodes_with_owned_docs,
            "leaves_without_owned_docs": self.leaves_without_owned_docs,
            "links_by_role": self.links_by_role,
        }


def coverage(org: Organization, ownership: DocumentOwnership, corpus_ids: list[str]) -> CoverageReport:
    mapped = [d for d in corpus_ids if ownership.owner_of(DocumentId(d)) is not None]
    unmapped = [d for d in corpus_ids if d not in mapped]
    owners = sorted({str(ownership.owner_of(DocumentId(d))) for d in mapped})
    leaves_without = sorted(
        str(n.identifier)
        for n in org.leaves()
        if not ownership.documents_of(n.identifier, OwnershipRole.OWNER, OwnershipRole.CO_OWNER)
    )
    roles = {r.value: sum(1 for l in ownership.links if l.role is r) for r in OwnershipRole}
    return CoverageReport(len(corpus_ids), mapped, unmapped, owners, leaves_without, roles)


def scope_sizes(
    org: Organization, ownership: DocumentOwnership, catalog: dict[str, tuple[str, str]]
) -> dict[str, dict[str, int]]:
    conf = {k: Confidentiality(normalize_confidentiality(v[1]) or "internal") for k, v in catalog.items()}
    resolver = ScopeResolver(org)
    out: dict[str, dict[str, int]] = {}
    for node in org.active_nodes():
        scope = resolver.resolve(node.identifier)
        out[str(node.identifier)] = {
            "visible_nodes": len(scope.visible_nodes),
            "visible_documents": len(resolver.visible_documents(node.identifier, ownership, conf)),
        }
    return out
