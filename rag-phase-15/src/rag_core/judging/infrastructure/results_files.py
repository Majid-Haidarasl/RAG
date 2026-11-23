"""Find the newest result file of an earlier phase (``results/phase-08/rag-demo-*.json``)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def latest_result(directory: Path, pattern: str) -> Path | None:
    directory = Path(directory)
    if not directory.is_dir():
        return None
    files = sorted(p for p in directory.glob(pattern) if p.is_file())
    return files[-1] if files else None


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}
