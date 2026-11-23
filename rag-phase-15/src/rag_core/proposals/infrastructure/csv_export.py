"""CSV export of one RFP's tables and the read-back check.

Files (UTF-8 with BOM so spreadsheet programs show Persian text correctly):
``<csv_dir>/<rfp_id>/rfp_requirements.csv``, ``proposals.csv``,
``evaluation.csv``, ``feedback.csv`` and ``knowledge_links.csv``. Lists are
joined with ``;``.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

TABLES: dict[str, tuple[str, ...]] = {
    "rfp_requirements": ("requirement_id", "rfp_id", "section", "mandatory", "answered_in", "statement_en",
                         "statement_fa", "evidence"),
    "proposals": ("proposal_id", "rfp_id", "vendor_en", "vendor_fa", "price_mtoman", "duration_weeks", "technology",
                  "version", "sections", "evidence"),
    "evaluation": ("row_id", "proposal_id", "criterion_id", "weight", "score", "contribution", "weighted",
                   "published", "rank", "compliant"),
    "feedback": ("row_id", "proposal_id", "language", "chars", "text"),
    "knowledge_links": ("link_id", "rfp_id", "node", "executor", "requirements", "evidence", "valid"),
}
ID_COLUMN = {"rfp_requirements": "requirement_id", "proposals": "proposal_id", "evaluation": "row_id",
             "feedback": "row_id", "knowledge_links": "link_id"}


def cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return ";".join(str(v) for v in value)
    return str(value)


def _safe(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name)


def export_tables(tables: Mapping[str, Sequence[Mapping[str, Any]]], csv_dir: Path, rfp_id: str) -> list[Path]:
    folder = Path(csv_dir) / _safe(rfp_id)
    folder.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, columns in TABLES.items():
        path = folder / f"{name}.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(columns), extrasaction="ignore")
            writer.writeheader()
            for row in tables.get(name, []):
                writer.writerow({c: cell(row.get(c)) for c in columns})
        written.append(path)
    return written


def read_table(csv_dir: Path, rfp_id: str, name: str) -> list[dict[str, str]]:
    path = Path(csv_dir) / _safe(rfp_id) / f"{name}.csv"
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def round_trip_problems(tables: Mapping[str, Sequence[Mapping[str, Any]]], csv_dir: Path, rfp_id: str) -> list[str]:
    problems: list[str] = []
    for name, columns in TABLES.items():
        try:
            back = read_table(csv_dir, rfp_id, name)
        except OSError as exc:
            problems.append(f"{name}: {type(exc).__name__}")
            continue
        rows = list(tables.get(name, []))
        if len(back) != len(rows):
            problems.append(f"{name}: {len(back)} rows read, {len(rows)} written")
            continue
        for want, got in zip(rows, back):
            for c in columns:
                if cell(want.get(c)) != got.get(c, ""):
                    problems.append(f"{name}:{cell(want.get(ID_COLUMN[name]))}:{c}")
                    break
    return problems
