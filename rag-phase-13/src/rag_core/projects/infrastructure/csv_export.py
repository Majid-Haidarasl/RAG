"""CSV export of one cycle's tracking tables and the read-back check.

Files (UTF-8 with BOM so spreadsheet programs show Persian text correctly):
``<csv_dir>/<cycle>/projects.csv``, ``records.csv``, ``gaps.csv`` and
``priorities.csv``. Lists are joined with ``;``.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

TABLES: dict[str, tuple[str, ...]] = {
    "projects": ("project_id", "name_en", "name_fa", "owner_node", "status", "health", "progress_percent",
                 "remaining_mtoman", "contract_value_mtoman", "issues", "open_issues", "blocked_subissues"),
    "records": ("record_id", "kind", "state", "project", "title_en", "title_fa", "issues", "nodes", "evidence",
                "conditions"),
    "gaps": ("gap_id", "rule", "kind", "severity", "subject", "issue_id", "title_en", "title_fa", "nodes",
             "documents", "detail"),
    "priorities": ("rank", "issue_id", "score", "key", "top_factors", "title_en", "title_fa"),
}
ID_COLUMN = {"projects": "project_id", "records": "record_id", "gaps": "gap_id", "priorities": "issue_id"}


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return ";".join(str(v) for v in value)
    return str(value)


def export_tables(tables: Mapping[str, Sequence[Mapping[str, Any]]], csv_dir: Path, cycle_id: str) -> list[Path]:
    folder = Path(csv_dir) / cycle_id
    folder.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, columns in TABLES.items():
        path = folder / f"{name}.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(columns), extrasaction="ignore")
            writer.writeheader()
            for row in tables.get(name, []):
                writer.writerow({c: _cell(row.get(c)) for c in columns})
        written.append(path)
    return written


def read_table(csv_dir: Path, cycle_id: str, name: str) -> list[dict[str, str]]:
    path = Path(csv_dir) / cycle_id / f"{name}.csv"
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def round_trip_problems(tables: Mapping[str, Sequence[Mapping[str, Any]]], csv_dir: Path, cycle_id: str) -> list[str]:
    problems: list[str] = []
    for name, columns in TABLES.items():
        try:
            back = read_table(csv_dir, cycle_id, name)
        except OSError as exc:
            problems.append(f"{name}: {type(exc).__name__}")
            continue
        rows = list(tables.get(name, []))
        if len(back) != len(rows):
            problems.append(f"{name}: {len(back)} rows read, {len(rows)} written")
            continue
        for want, got in zip(rows, back):
            for c in columns:
                if _cell(want.get(c)) != got.get(c, ""):
                    problems.append(f"{name}:{_cell(want.get(ID_COLUMN[name]))}:{c}")
                    break
    return problems
