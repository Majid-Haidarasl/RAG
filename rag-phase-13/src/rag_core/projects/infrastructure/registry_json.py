"""JSON adapter: data/projects/project-registry.json -> ``ProjectRegistry``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rag_core.projects.domain.model import Project, ProjectRegistry, ScorecardDimension, TrackRecord
from rag_core.shared_kernel.errors import InvariantError

REGISTRY_FILE = "project-registry.json"

PROJECT_KEYS = frozenset({"id", "code_source", "name_en", "name_fa", "customer", "owner_node", "nodes", "contract_ref",
                          "contract_value_mtoman", "remaining_mtoman", "progress_percent", "status", "primary_issue",
                          "issues", "evidence"})
RECORD_KEYS = frozenset({"id", "kind", "project", "state", "title_en", "title_fa", "statement_en", "statement_fa",
                         "conditions", "nodes", "people", "issues", "evidence", "validated_result", "risks",
                         "evidence_needed", "measures"})
SCORECARD_KEYS = frozenset({"id", "name_en", "name_fa", "state", "target_en", "owner", "evidence", "research"})


def _check_keys(rec: dict[str, Any], allowed: frozenset[str], label: str) -> None:
    unknown = sorted(set(rec) - allowed)
    if unknown:
        raise InvariantError(f"{label} {rec.get('id', '?')}: unknown keys {', '.join(unknown)}")


def _t(value: Any) -> tuple[str, ...]:
    return tuple(str(v) for v in (value or []))


def project_from_record(rec: dict[str, Any]) -> Project:
    _check_keys(rec, PROJECT_KEYS, "project")
    return Project(
        project_id=str(rec["id"]), name_en=str(rec.get("name_en", "")), name_fa=str(rec.get("name_fa", "")),
        owner_node=str(rec.get("owner_node", "")), progress_percent=int(rec.get("progress_percent", 0)),
        status=rec.get("status", "active"), customer=str(rec.get("customer", "")),
        code_source=str(rec.get("code_source", "registry")), nodes=_t(rec.get("nodes")),
        contract_ref=str(rec.get("contract_ref") or ""),
        contract_value_mtoman=rec.get("contract_value_mtoman"), remaining_mtoman=rec.get("remaining_mtoman"),
        primary_issue=str(rec.get("primary_issue") or ""), issues=_t(rec.get("issues")),
        evidence=_t(rec.get("evidence")),
    )


def track_record_from(rec: dict[str, Any]) -> TrackRecord:
    _check_keys(rec, RECORD_KEYS, "record")
    return TrackRecord(
        record_id=str(rec["id"]), kind=rec["kind"], state=rec.get("state", "open"),
        title_en=str(rec.get("title_en", "")), title_fa=str(rec.get("title_fa", "")),
        statement_en=str(rec.get("statement_en", "")), statement_fa=str(rec.get("statement_fa", "")),
        conditions=str(rec.get("conditions", "")), project=str(rec.get("project") or ""),
        nodes=_t(rec.get("nodes")), people=_t(rec.get("people")), issues=_t(rec.get("issues")),
        evidence=_t(rec.get("evidence")), validated_result=bool(rec.get("validated_result", False)),
        risks=_t(rec.get("risks")), evidence_needed=_t(rec.get("evidence_needed")), measures=_t(rec.get("measures")),
    )


def dimension_from(rec: dict[str, Any]) -> ScorecardDimension:
    _check_keys(rec, SCORECARD_KEYS, "scorecard dimension")
    return ScorecardDimension(
        dimension_id=str(rec["id"]), name_en=str(rec.get("name_en", "")), name_fa=str(rec.get("name_fa", "")),
        state=rec.get("state", "open"), target_en=str(rec.get("target_en", "")), owner=str(rec.get("owner", "")),
        evidence=_t(rec.get("evidence")), research=str(rec.get("research") or ""),
    )


def registry_from_dict(data: dict[str, Any]) -> ProjectRegistry:
    return ProjectRegistry(
        cycle=str(data.get("cycle", "")), cutoff=str(data.get("cutoff", "")),
        projects=tuple(project_from_record(p) for p in data.get("projects", [])),
        records=tuple(track_record_from(r) for r in data.get("records", [])),
        scorecard=tuple(dimension_from(d) for d in data.get("scorecard", [])),
    )


def read_registry_dict(directory: Path) -> dict[str, Any]:
    return json.loads((Path(directory) / REGISTRY_FILE).read_text(encoding="utf-8"))


class JsonProjectRegistry:
    def __init__(self, directory: Path) -> None:
        self.dir = Path(directory)

    def raw(self) -> dict[str, Any]:
        return read_registry_dict(self.dir)

    def load(self) -> ProjectRegistry:
        return registry_from_dict(self.raw())
