"""Deterministic CSV round-trip for a TransferPackage (policy item 17)."""

from __future__ import annotations

import csv
from io import StringIO

from rag_core.knowledge.domain.services import Citation
from rag_core.shared_kernel.identifiers import DocumentId, NodeIdentifier
from rag_core.shared_kernel.language import LanguageCode
from rag_core.shared_kernel.layer import LayerIndex
from rag_core.transfer.domain.model import (
    PackageStatus,
    TransferDetailLevel,
    TransferPackage,
)


FIELD_ORDER = ("risks", "decisions_requested", "source_references", "key_issues", "summary")


def package_to_csv(package: TransferPackage) -> str:
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["key", "value"])
    writer.writerow(["source_node", str(package.source_node)])
    writer.writerow(["target_node", str(package.target_node)])
    writer.writerow(["target_layer", str(package.target_layer.value)])
    writer.writerow(["detail_level", package.detail_level.value])
    writer.writerow(["status", package.status.value])
    for key in FIELD_ORDER:
        if key in package.fields:
            writer.writerow([key, package.fields[key]])
    for key, value in package.fields.items():
        if key not in FIELD_ORDER:
            writer.writerow([key, value])
    writer.writerow(["citations", " | ".join(str(c) for c in package.citations)])
    return buffer.getvalue()


def package_from_csv(text: str) -> TransferPackage:
    reader = csv.reader(StringIO(text))
    header = next(reader)
    if header != ["key", "value"]:
        raise ValueError("unexpected CSV header")
    data = {row[0]: row[1] for row in reader if row}
    citations: list[Citation] = []
    raw_citations = data.pop("citations", "")
    if raw_citations.strip():
        for token in raw_citations.split(" | "):
            doc, _, rest = token.partition("@")
            version, _, chunk = rest.partition("#")
            citations.append(
                Citation(
                    document_id=DocumentId(doc),
                    version=version,
                    language=LanguageCode.FA,
                    chunk_id=chunk,
                )
            )
    fields = {k: v for k, v in data.items() if k not in {
        "source_node", "target_node", "target_layer", "detail_level", "status"
    }}
    package = TransferPackage(
        source_node=NodeIdentifier(data["source_node"]),
        target_node=NodeIdentifier(data["target_node"]),
        target_layer=LayerIndex(int(data["target_layer"])),
        detail_level=TransferDetailLevel(data["detail_level"]),
        fields=fields,
        citations=tuple(citations),
        status=PackageStatus(data["status"]),
    )
    return package
