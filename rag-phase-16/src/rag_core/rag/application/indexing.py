"""Build index records from Phase 4/5 output and refresh the persistent index.

* ``records_from_lifecycle``: every chunk of every version in the Phase 5
  lifecycle becomes a ``ChunkRecord`` (status and version status kept, so
  the retriever's ``active_only`` filter can exclude stale/retired chunks).
  Page / paragraph anchors come from the Phase 4 ``TextChunk`` of the same
  chunk id when the ingested document is the version's source.
* Exact duplicates across documents (same Phase 5 normalized hash, same
  language) share ``duplicate_of`` = the smallest key of the group.
* ``IndexBuilder.refresh`` embeds only active records whose (key, hash,
  model) is not already stored, and removes vectors that are no longer
  active.
"""

from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace

from rag_core.ingestion.domain.catalog import lookup
from rag_core.ingestion.domain.model import IngestedDocument, TextChunk
from rag_core.knowledge.domain.model import KnowledgeItem, VersionStatus
from rag_core.rag.domain.lexical import Bm25Index
from rag_core.rag.domain.ports import EmbeddingPort, ScopePort
from rag_core.rag.domain.records import ChunkRecord, record_key
from rag_core.rag.domain.retriever import HybridRetriever, RetrievalConfig
from rag_core.rag.domain.vector import InMemoryVectorIndex
from rag_core.rag.infrastructure.memory import InMemoryChunkStore


def _anchor_fields(chunk: TextChunk | None) -> dict[str, int | None]:
    if chunk is None or not chunk.anchors:
        return {"page": None, "paragraph": None, "table": None}
    first = chunk.anchors[0]
    return {
        "page": first.page,
        "paragraph": first.paragraph_index,
        "table": first.table_index,
    }


def records_from_lifecycle(
    items: Iterable[KnowledgeItem],
    documents: Iterable[IngestedDocument] = (),
    *,
    owner_of: Callable[[str], str | None] | None = None,
    layer_of: Callable[[str], int | None] | None = None,
) -> list[ChunkRecord]:
    by_source: dict[tuple[str, str, str], TextChunk] = {}
    sha_of: dict[tuple[str, str], str] = {}
    for doc in documents:
        if doc.language is None:
            continue
        sha_of[(doc.document_id, doc.language.value)] = doc.file_sha256
        for ch in doc.chunks:
            by_source[(doc.file_sha256, doc.language.value, ch.chunk_id)] = ch
    records: list[ChunkRecord] = []
    for item in items:
        doc_id = str(item.document_id)
        entry = lookup(doc_id)
        owner = (owner_of(doc_id) if owner_of else None) or str(item.owning_node)
        layer = layer_of(owner) if layer_of else None
        for version in item.versions:
            lang = version.language.value
            for chunk in version.chunks:
                anchor = by_source.get((version.file_sha256, lang, chunk.chunk_id))
                records.append(
                    ChunkRecord(
                        key=record_key(doc_id, str(version.tag), lang, chunk.order),
                        document_id=doc_id,
                        language=lang,
                        version=str(version.tag),
                        order=chunk.order,
                        text=chunk.text,
                        heading_path=chunk.heading_path,
                        owner_node=owner,
                        layer=layer,
                        knowledge_class=entry.doc_type
                        if entry
                        else item.scope.subject_domain,
                        confidentiality=item.confidentiality.value,
                        status=chunk.status.value,
                        version_status=VersionStatus(version.status).value,
                        content_hash=chunk.normalized_hash,
                        **_anchor_fields(anchor),
                    )
                )
    return mark_exact_duplicates(records)


def mark_exact_duplicates(records: list[ChunkRecord]) -> list[ChunkRecord]:
    groups: dict[tuple[str, str], list[ChunkRecord]] = defaultdict(list)
    for r in records:
        if r.is_active and r.content_hash:
            groups[(r.language, r.content_hash)].append(r)
    canonical: dict[str, str] = {}
    for members in groups.values():
        if len(members) < 2:
            continue
        head = min(m.key for m in members)
        for m in members:
            if m.key != head:
                canonical[m.key] = head
    return [
        replace(r, duplicate_of=canonical[r.key]) if r.key in canonical else r
        for r in records
    ]


@dataclass
class IndexBuildReport:
    records: int = 0
    active: int = 0
    embedded: int = 0
    reused: int = 0
    removed: int = 0
    dim: int | None = None
    model: str = ""
    seconds: float = 0.0
    embed_seconds: float = 0.0
    batches: int = 0
    by_language: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "records": self.records,
            "active": self.active,
            "embedded": self.embedded,
            "reused": self.reused,
            "removed": self.removed,
            "dim": self.dim,
            "model": self.model,
            "seconds": round(self.seconds, 3),
            "embed_seconds": round(self.embed_seconds, 3),
            "batches": self.batches,
            "active_by_language": self.by_language,
        }


class IndexBuilder:
    """Refresh a ``SqliteIndexStore``-like store (records + vectors)."""

    def __init__(
        self, store, embedder: EmbeddingPort, model: str, batch_size: int = 16
    ) -> None:
        self.store = store
        self.embedder = embedder
        self.model = model
        self.batch_size = batch_size

    def refresh(
        self,
        records: list[ChunkRecord],
        progress: Callable[[int, int], None] | None = None,
    ) -> IndexBuildReport:
        t0 = time.perf_counter()
        report = IndexBuildReport(records=len(records), model=self.model)
        self.store.replace_records(records)
        report.removed += self.store.delete_other_models(self.model)
        active = [r for r in records if r.is_active]
        report.active = len(active)
        for r in active:
            report.by_language[r.language] = report.by_language.get(r.language, 0) + 1
        have = self.store.vector_fingerprints(self.model)
        active_keys = {r.key for r in active}
        stale = [k for k in have if k not in active_keys]
        if stale:
            self.store.delete_vectors(stale)
            report.removed += len(stale)
        todo = [r for r in active if have.get(r.key) != r.content_hash]
        report.reused = len(active) - len(todo)
        t = time.perf_counter()
        for i in range(0, len(todo), self.batch_size):
            batch = todo[i : i + self.batch_size]
            vectors = self.embedder.embed([r.text for r in batch])
            self.store.put_vectors(
                self.model, [(r.key, r.content_hash, v) for r, v in zip(batch, vectors)]
            )
            report.embedded += len(batch)
            report.batches += 1
            if vectors:
                report.dim = len(vectors[0])
            if progress:
                progress(report.embedded, len(todo))
        report.embed_seconds = time.perf_counter() - t
        if report.dim is None and active:
            index = self.store.load_vectors(self.model)
            report.dim = index.dim
        self.store.set_meta("embedding_model", self.model)
        self.store.set_meta("records", str(len(records)))
        report.seconds = time.perf_counter() - t0
        return report


def build_retriever(
    records: list[ChunkRecord],
    *,
    vectors: InMemoryVectorIndex | None = None,
    embedder: EmbeddingPort | None = None,
    scope: ScopePort | None = None,
    config: RetrievalConfig | None = None,
) -> HybridRetriever:
    """Wire store + BM25 (active records only) + optional dense index."""
    store = InMemoryChunkStore(records)
    lexical = Bm25Index((r.key, r.text) for r in records if r.is_active)
    return HybridRetriever(store, lexical, vectors, embedder, scope, config)
