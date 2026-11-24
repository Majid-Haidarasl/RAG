"""Corpus → index records: Phase 4 ingest + Phase 5 lifecycle + Phase 6 scope.

Only the official ``corpus/fa`` and ``corpus/en`` files are indexed. The
``corpus/derived`` renditions are PDF/DOC exports of the same documents
(Phase 5 matched every one to its DOCX), so indexing them would only add
duplicates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
import time

from rag_core.hierarchy.application.workflows import catalog_index, load_and_validate
from rag_core.hierarchy.domain.validation import normalize_confidentiality
from rag_core.ingestion.application.pipeline import ingest_file
from rag_core.knowledge.application.lifecycle import KnowledgeLifecycleService
from rag_core.rag.application.indexing import records_from_lifecycle
from rag_core.rag.domain.records import ChunkRecord
from rag_core.rag.infrastructure.scope_acl import HierarchyScope
from rag_core.shared_kernel.confidentiality import Confidentiality
from rag_core.shared_kernel.errors import DomainError

CORPUS_EFFECTIVE = date(2024, 10, 1)  # catalog 1403-07
FORMATS = (".docx", ".doc", ".pdf")


@dataclass
class CorpusIndexInput:
    records: list[ChunkRecord]
    scope: HierarchyScope
    files: int
    failures: list[dict[str, str]] = field(default_factory=list)
    seconds: float = 0.0


def load_scope(registry_dir: Path) -> HierarchyScope:
    loaded = load_and_validate(registry_dir)
    if loaded.organization is None or loaded.ownership is None:
        raise DomainError(f"registry invalid: {len(loaded.report.errors)} error(s)")
    conf = {
        k: Confidentiality(normalize_confidentiality(v[1]) or "internal")
        for k, v in catalog_index().items()
    }
    return HierarchyScope(loaded.organization, loaded.ownership, conf)


def build_corpus_records(root: Path) -> CorpusIndexInput:
    t0 = time.perf_counter()
    scope = load_scope(root / "data" / "registry")
    paths = [
        p
        for lang in ("fa", "en")
        for p in sorted((root / "corpus" / lang).glob("*"))
        if p.is_file() and p.suffix.lower() in FORMATS
    ]
    docs = []
    failures: list[dict[str, str]] = []
    for path in paths:
        try:
            docs.append(ingest_file(path, repo_root=root))
        except Exception as exc:  # noqa: BLE001 - reported, never hidden
            failures.append(
                {
                    "path": str(path.relative_to(root)),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    lifecycle = KnowledgeLifecycleService()
    for doc in docs:
        lifecycle.ingest(doc, effective_from=CORPUS_EFFECTIVE)
    records = records_from_lifecycle(
        lifecycle.items(), docs, owner_of=scope.owner_of, layer_of=scope.layer_of
    )
    return CorpusIndexInput(
        records, scope, len(paths), failures, time.perf_counter() - t0
    )
