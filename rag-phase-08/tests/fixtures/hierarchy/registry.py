"""Helpers for Phase 6 tests: the shipped registry CSVs and mutable row copies."""

from __future__ import annotations

import copy
from pathlib import Path

from rag_core.hierarchy.application.workflows import LoadedRegistry, catalog_index, load_and_validate
from rag_core.hierarchy.infrastructure.registry_csv import CsvRegistryLoader, RegistryRows

REPO = Path(__file__).resolve().parents[3]
REGISTRY_DIR = REPO / "data" / "registry"


def shipped_rows() -> RegistryRows:
    return copy.deepcopy(CsvRegistryLoader(REGISTRY_DIR).rows())


def shipped_registry() -> LoadedRegistry:
    return load_and_validate(REGISTRY_DIR, catalog_index())


def node_row(rows: RegistryRows, node_id: str) -> dict[str, str]:
    return next(r for r in rows.nodes if r["node_id"] == node_id)


def layer_row(rows: RegistryRows, index: int) -> dict[str, str]:
    return next(r for r in rows.layers if int(r["layer_index"]) == index)
