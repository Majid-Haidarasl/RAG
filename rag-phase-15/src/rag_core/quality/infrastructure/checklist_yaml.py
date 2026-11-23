"""``config/release-checklist.yaml`` -> list of ``Deliverable``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from rag_core.quality.domain.checklist import Deliverable
from rag_core.shared_kernel.errors import InvariantError

KEYS = {"spec", "status", "paths", "note"}


def deliverables_from_dict(data: Any) -> list[Deliverable]:
    if not isinstance(data, dict) or not isinstance(data.get("phases"), list):
        raise InvariantError("release checklist needs a 'phases' list")
    out: list[Deliverable] = []
    for ph in data["phases"]:
        if not isinstance(ph, dict) or "phase" not in ph:
            raise InvariantError("every checklist phase needs 'phase'")
        number = ph["phase"]
        if isinstance(number, bool) or not isinstance(number, int):
            raise InvariantError(f"phase number must be an integer, got {number!r}")
        for d in ph.get("deliverables") or []:
            if not isinstance(d, dict):
                raise InvariantError(f"phase {number}: a deliverable must be a mapping")
            unknown = sorted(set(d) - KEYS)
            if unknown:
                raise InvariantError(f"phase {number}: unknown deliverable keys {', '.join(unknown)}")
            paths = d.get("paths") or []
            if isinstance(paths, str):
                paths = [paths]
            out.append(Deliverable(number, str(d.get("spec", "")), str(d.get("status", "")),
                                   tuple(str(p) for p in paths), str(d.get("note", "") or "")))
    return out


def load_deliverables(path: Path) -> list[Deliverable]:
    with Path(path).open(encoding="utf-8") as fh:
        return deliverables_from_dict(yaml.safe_load(fh))
