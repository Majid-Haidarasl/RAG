"""CSV adapter: data/registry/*.csv → Organization, transfer requirements, ownership."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from rag_core.hierarchy.domain.model import Layer, Node, NodeStatus, NodeType, Organization
from rag_core.hierarchy.domain.ownership import DocumentOwnership, OwnershipLink, OwnershipRole
from rag_core.hierarchy.domain.transfer import TransferDirection, TransferRequirement
from rag_core.hierarchy.domain.validation import normalize_confidentiality
from rag_core.shared_kernel.confidentiality import Confidentiality
from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.identifiers import DocumentId, NodeIdentifier
from rag_core.shared_kernel.layer import LayerIndex

LAYER_FILE = "layer-registry.csv"
NODE_FILE = "node-registry.csv"
DOC_MAP_FILE = "document-node-map.csv"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [{k: (v or "") for k, v in row.items()} for row in csv.DictReader(handle)]


def _split(value: str) -> tuple[str, ...]:
    return tuple(p.strip() for p in value.split(";") if p.strip())


def _int_or_none(value: str) -> int | None:
    value = value.strip()
    return int(value) if value else None


def layer_from_row(row: dict[str, str]) -> Layer:
    index = LayerIndex(int(row["layer_index"]))
    transfer = None
    if row.get("transfer_direction", "").strip():
        transfer = TransferRequirement(
            layer=index,
            direction=TransferDirection(row["transfer_direction"].strip()),
            target=LayerIndex(int(row["transfer_target"].strip()[1:])),
            must_hand_over=row.get("must_hand_over", ""),
            min_artefacts=_split(row.get("min_artefacts", "")),
            approvals=_split(row.get("approvals_required", "")),
            required_feedback=row.get("required_feedback", ""),
            sources=_split(row.get("transfer_sources", "")),
        )
    return Layer(
        index=index,
        code=row["layer_code"].strip(),
        name_en=row["layer_name_en"].strip(),
        name_fa=row["layer_name_fa"].strip(),
        role=row.get("layer_role", ""),
        min_judge_score=_int_or_none(row.get("min_judge_score", "")) or 0,
        max_package_words=_int_or_none(row.get("max_package_words", "")),
        default_detail_level=row.get("default_detail_level_received", "").strip(),
        knowledge_needed_from_children=row.get("knowledge_needed_from_children", ""),
        required_transfer_format=row.get("required_transfer_format", ""),
        source_citation_level=row.get("source_citation_level", ""),
        default_confidentiality=normalize_confidentiality(row.get("default_confidentiality", "")),
        transfer=transfer,
    )


def node_from_row(row: dict[str, str], layers: dict[int, Layer]) -> Node:
    parent = row.get("parent_node_id", "").strip()
    escalation = row.get("escalation_node_id", "").strip()
    conf = normalize_confidentiality(row.get("confidentiality", "")) or "internal"
    return Node(
        identifier=NodeIdentifier(row["node_id"].strip()),
        name_en=row["node_name_en"].strip(),
        name_fa=row["node_name_fa"].strip(),
        node_type=NodeType(row["node_type"].strip()),
        layer=layers[int(row["layer_index"])].index,
        parent_id=NodeIdentifier(parent) if parent else None,
        is_leaf=row.get("is_leaf", "").strip().lower() == "true",
        activity_domain=row.get("activity_domain", ""),
        cost_center=row.get("cost_center", ""),
        confidentiality=Confidentiality(conf),
        status=NodeStatus(row.get("status", "").strip() or "active"),
        escalation_id=NodeIdentifier(escalation) if escalation else None,
        head_or_key_contact=row.get("head_or_key_contact", ""),
        transfer_detail_level_to_parent=row.get("transfer_detail_level_to_parent", "").strip(),
        source_docs=_split(row.get("source_docs", "")),
    )


@dataclass(frozen=True)
class RegistryRows:
    layers: list[dict[str, str]]
    nodes: list[dict[str, str]]
    doc_map: list[dict[str, str]]


class CsvRegistryLoader:
    def __init__(self, registry_dir: Path) -> None:
        self.dir = Path(registry_dir)

    def rows(self) -> RegistryRows:
        doc_map_path = self.dir / DOC_MAP_FILE
        return RegistryRows(
            read_rows(self.dir / LAYER_FILE),
            read_rows(self.dir / NODE_FILE),
            read_rows(doc_map_path) if doc_map_path.exists() else [],
        )

    def build_organization(self, rows: RegistryRows | None = None) -> Organization:
        """Build the aggregate; nodes are registered parents-first (domain invariants apply)."""
        rows = rows or self.rows()
        org = Organization()
        for row in sorted(rows.layers, key=lambda r: int(r["layer_index"])):
            org.register_layer(layer_from_row(row))
        pending = [node_from_row(r, org.layers) for r in rows.nodes]
        # Escalation targets are attached after all nodes exist.
        escalations = {n.identifier: n.escalation_id for n in pending}
        for n in pending:
            n.escalation_id = None
        while pending:
            ready = [n for n in pending if n.parent_id is None or n.parent_id in org]
            if not ready:
                raise InvariantError(f"unresolvable parents for {[str(n.identifier) for n in pending]}")
            for node in ready:
                org.register_node(node)
                pending.remove(node)
        for nid, esc in escalations.items():
            if esc is not None:
                org.get(esc)
                org.get(nid).escalation_id = esc
        return org

    def build_ownership(self, rows: RegistryRows | None = None) -> DocumentOwnership:
        rows = rows or self.rows()
        ownership = DocumentOwnership()
        for row in rows.doc_map:
            ownership.add(
                OwnershipLink(
                    DocumentId(row["document_id"]),
                    NodeIdentifier(row["node_id"]),
                    OwnershipRole(row["role"].strip()),
                    row.get("source", ""),
                )
            )
        return ownership


def write_doc_map(path: Path, ownership: DocumentOwnership) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["document_id", "node_id", "role", "source"])
        for link in sorted(ownership.links, key=lambda l: (l.document_id.value, l.role != OwnershipRole.OWNER, l.node_id.value)):
            writer.writerow([link.document_id.value, link.node_id.value, link.role.value, link.source])
