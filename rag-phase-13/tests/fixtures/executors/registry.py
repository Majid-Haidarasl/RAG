"""Phase 9 test helpers: the shipped executor registry and small factories."""

from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path

from rag_core.executors.application.services import load_executor_registry
from rag_core.executors.domain.model import Executor, ExpertiseTag, ReferralCapacity
from rag_core.executors.infrastructure.hierarchy_acl import HierarchyTeamDirectory
from rag_core.shared_kernel.identifiers import DocumentId, ExecutorId, NodeIdentifier

REPO = Path(__file__).resolve().parents[3]
EXECUTORS_DIR = REPO / "data" / "executors"
REGISTRY_DIR = REPO / "data" / "registry"


@lru_cache(maxsize=1)
def _teams() -> HierarchyTeamDirectory:
    return HierarchyTeamDirectory.from_registry(REGISTRY_DIR)


def team_directory() -> HierarchyTeamDirectory:
    return _teams()


@lru_cache(maxsize=1)
def _executors() -> tuple[Executor, ...]:
    loaded = load_executor_registry(EXECUTORS_DIR, _teams())
    assert loaded.report.ok, loaded.report.errors
    return tuple(loaded.executors)


def shipped_executors() -> list[Executor]:
    return copy.deepcopy(list(_executors()))


def raw_records() -> list[dict]:
    data = json.loads(
        (EXECUTORS_DIR / "executor-registry.json").read_text(encoding="utf-8")
    )
    return copy.deepcopy(data["executors"])


def make_executor(
    ident: str = "EX-TEST-PERSON",
    name: str = "Test Person",
    node: str = "N-SW-WEB",
    *,
    specialty: tuple[str, ...] = (),
    domains: tuple[str, ...] = ("web architecture",),
    expertise: tuple[str, ...] = (),
    docs: tuple[str, ...] = (),
    hours: int | None = 20,
    aliases: tuple[str, ...] = (),
) -> Executor:
    return Executor(
        identifier=ExecutorId(ident),
        display_name=name,
        home_node=NodeIdentifier(node),
        expertise=tuple(ExpertiseTag(t) for t in expertise),
        allowed_referral_domains=domains,
        capacity=ReferralCapacity(hours),
        specialty=specialty,
        knowledge_documents=tuple(DocumentId(d) for d in docs),
        aliases=aliases,
    )
