"""``coverage json`` output (coverage.py 7.x) -> ``CoverageReport``.

Only the fields that coverage.py has written for years are read:
``files.<path>.summary.{num_statements, covered_lines}``, the optional branch
fields ``num_branches`` / ``covered_branches`` and ``missing_lines``, and
``meta.branch_coverage`` / ``meta.version``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rag_core.quality.domain.coverage import CoverageReport, ModuleCoverage
from rag_core.shared_kernel.errors import InvariantError


def _int(summary: dict[str, Any], key: str, where: str) -> int:
    value = summary.get(key, 0)
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvariantError(f"{where}: {key} must be an integer")
    return value


def module_from_entry(path: str, entry: Any) -> ModuleCoverage:
    if not isinstance(entry, dict) or not isinstance(entry.get("summary"), dict):
        raise InvariantError(f"{path}: coverage entry without a summary")
    s = entry["summary"]
    if "num_statements" not in s or "covered_lines" not in s:
        raise InvariantError(f"{path}: summary needs num_statements and covered_lines")
    missing = entry.get("missing_lines") or []
    return ModuleCoverage(path.replace("\\", "/"), _int(s, "num_statements", path), _int(s, "covered_lines", path),
                          _int(s, "num_branches", path), _int(s, "covered_branches", path),
                          tuple(int(n) for n in missing))


def report_from_dict(data: Any, *, package: str = "rag_core") -> CoverageReport:
    """Modules of ``package`` only (tests and scripts are not part of the gate)."""
    if not isinstance(data, dict) or not isinstance(data.get("files"), dict):
        raise InvariantError("coverage json needs a 'files' mapping")
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    mods = [module_from_entry(p, e) for p, e in sorted(data["files"].items())
            if f"/{package}/" in "/" + p.replace("\\", "/")]
    return CoverageReport(tuple(mods), bool(meta.get("branch_coverage")), str(meta.get("version", "")))


def load_coverage_report(path: Path, *, package: str = "rag_core") -> CoverageReport | None:
    """``None`` when the file does not exist (coverage was not measured)."""
    path = Path(path)
    if not path.is_file():
        return None
    return report_from_dict(json.loads(path.read_text(encoding="utf-8")), package=package)
