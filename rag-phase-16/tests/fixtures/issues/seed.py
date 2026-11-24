"""Phase 7 test helpers: the shipped hierarchy + issue registries (read-only)."""

from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path

from rag_core.issues.application.services import load_issue_registry
from rag_core.issues.domain.model import Issue
from rag_core.issues.infrastructure.hierarchy_acl import HierarchyOrgDirectory

REPO = Path(__file__).resolve().parents[3]
ISSUES_DIR = REPO / "data" / "issues"
REGISTRY_DIR = REPO / "data" / "registry"


@lru_cache(maxsize=1)
def _org() -> HierarchyOrgDirectory:
    return HierarchyOrgDirectory.from_registry(REGISTRY_DIR)


def org_directory() -> HierarchyOrgDirectory:
    return _org()


@lru_cache(maxsize=1)
def _issues() -> tuple[Issue, ...]:
    loaded = load_issue_registry(ISSUES_DIR, _org())
    assert loaded.report.ok, loaded.report.errors
    return tuple(loaded.issues)


def seed_issues() -> list[Issue]:
    return copy.deepcopy(list(_issues()))


def azarpakhsh() -> Issue:
    return next(i for i in seed_issues() if str(i.identifier) == "AR-ISS-024")


def raw_records() -> list[dict]:
    return copy.deepcopy(
        json.loads((ISSUES_DIR / "issue-registry.json").read_text(encoding="utf-8"))[
            "issues"
        ]
    )


def samples() -> list[dict]:
    return json.loads(
        (ISSUES_DIR / "new-issue-samples.json").read_text(encoding="utf-8")
    )["samples"]
