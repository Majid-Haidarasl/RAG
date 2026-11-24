"""CSV export of the latest packages: ``exports/transfer-packages/<cycle>/``.

* ``<SOURCE-NODE>.csv`` — one package in the Phase 3 key/value format
  (``package_to_csv``; UTF-8, Persian text preserved);
* ``latest-packages.csv`` — one row per latest package (index).

Files are rewritten from the store, so the export always equals the latest
revisions in SQLite. They are generated per run and not committed.
"""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
from typing import Any

from rag_core.knowledge.domain.services import Citation
from rag_core.shared_kernel.identifiers import DocumentId, NodeIdentifier
from rag_core.shared_kernel.language import LanguageCode
from rag_core.shared_kernel.layer import LayerIndex
from rag_core.transfer.domain.model import (
    PackageStatus,
    TransferDetailLevel,
    TransferPackage,
)
from rag_core.transfer.infrastructure.csv_format import package_from_csv, package_to_csv

INDEX_FILE = "latest-packages.csv"
INDEX_COLUMNS = (
    "cycle_id",
    "source_node",
    "target_node",
    "target_layer",
    "detail_level",
    "status",
    "revision",
    "items",
    "words_en",
    "words_fa",
    "content_hash",
    "created_at",
    "file",
)


def citation_from_text(text: str) -> Citation:
    doc, _, rest = text.partition("@")
    version, _, chunk = rest.partition("#")
    return Citation(DocumentId(doc), version, LanguageCode.FA, chunk_id=chunk)


def package_from_payload(payload: dict[str, Any]) -> TransferPackage:
    return TransferPackage(
        source_node=NodeIdentifier(payload["source_node"]),
        target_node=NodeIdentifier(payload["target_node"]),
        target_layer=LayerIndex(int(payload["target_layer"])),
        detail_level=TransferDetailLevel(payload["detail_level"]),
        fields=dict(payload["fields"]),
        citations=tuple(citation_from_text(c) for c in payload.get("citations", [])),
        status=PackageStatus(payload["status"]),
    )


def export_latest(
    rows: list[dict[str, Any]], out_dir: Path, cycle_id: str
) -> list[Path]:
    """Write one CSV per latest package plus the index; stale package files of this cycle are removed."""
    folder = Path(out_dir) / cycle_id
    folder.mkdir(parents=True, exist_ok=True)
    keep = {f"{r['source_node']}.csv" for r in rows} | {INDEX_FILE}
    for old in folder.glob("*.csv"):
        if old.name not in keep:
            old.unlink()
    written: list[Path] = []
    index_rows: list[list[str]] = []
    for r in rows:
        path = folder / f"{r['source_node']}.csv"
        path.write_text(
            package_to_csv(package_from_payload(r["payload"])), encoding="utf-8"
        )
        written.append(path)
        index_rows.append([str(r.get(c, "")) for c in INDEX_COLUMNS[:-1]] + [path.name])
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(INDEX_COLUMNS)
    writer.writerows(index_rows)
    index = folder / INDEX_FILE
    index.write_text(buffer.getvalue(), encoding="utf-8")
    written.append(index)
    return written


def round_trip_problems(
    rows: list[dict[str, Any]], out_dir: Path, cycle_id: str
) -> list[str]:
    """Read every exported package back and compare it with the stored payload."""
    problems: list[str] = []
    folder = Path(out_dir) / cycle_id
    for r in rows:
        path = folder / f"{r['source_node']}.csv"
        if not path.is_file():
            problems.append(f"{r['source_node']}: file missing")
            continue
        restored = package_from_csv(path.read_text(encoding="utf-8"))
        payload = r["payload"]
        if restored.fields != payload["fields"]:
            problems.append(f"{r['source_node']}: fields differ")
        if restored.status.value != payload["status"]:
            problems.append(f"{r['source_node']}: status differs")
        if [str(c) for c in restored.citations] != list(payload.get("citations", [])):
            problems.append(f"{r['source_node']}: citations differ")
        if str(restored.target_node) != payload["target_node"]:
            problems.append(f"{r['source_node']}: target differs")
    index = folder / INDEX_FILE
    if not index.is_file():
        problems.append("index file missing")
    else:
        lines = list(csv.reader(StringIO(index.read_text(encoding="utf-8"))))
        if len(lines) - 1 != len(rows):
            problems.append(f"index has {len(lines) - 1} rows, expected {len(rows)}")
    return problems
