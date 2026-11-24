"""Hybrid, node-scoped retrieval: filters → BM25 + dense → RRF → dedup.

Orchestration (one question asked from node X):

1. Candidate keys = records admitted by the metadata filters (language,
   doc_id, layer, knowledge class, active versions only) whose document is
   in X's Phase 6 retrieval scope.
2. Lexical ranking (BM25) and vector ranking (cosine) over the candidates,
   ``candidate_k`` each.
3. Reciprocal Rank Fusion of the two rankings.
4. Duplicate collapse with Phase 5 information: records of one exact
   duplicate group (normalized sha256), or word-3-shingle Jaccard ≥ the
   Phase 5 near threshold (0.80), keep only the best-ranked hit. FA/EN
   renditions of one document are never duplicates of each other.
5. Top ``top_k`` hits.

An out-of-scope probe runs the same ranking over admitted records the node
may NOT see. Only owners and scores leave the probe (never text), so the
Q&A service can suggest an escalation without leaking content.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time

from rag_core.knowledge.domain.dedup import DedupConfig
from rag_core.knowledge.domain.fingerprint import jaccard, shingles
from rag_core.rag.domain.fusion import DEFAULT_RRF_K, reciprocal_rank_fusion
from rag_core.rag.domain.lexical import Bm25Index
from rag_core.rag.domain.ports import (
    ChunkStorePort,
    EmbeddingPort,
    ScopePort,
    VectorIndexPort,
)
from rag_core.rag.domain.records import ChunkRecord, SearchFilters
from rag_core.shared_kernel.errors import InvariantError, NotFoundError


@dataclass(frozen=True)
class RetrievalConfig:
    top_k: int = 5
    candidate_k: int = 30
    rrf_k: int = DEFAULT_RRF_K
    lexical_weight: float = 1.0
    vector_weight: float = 1.0
    near_duplicate_threshold: float = DedupConfig().near_threshold
    probe_k: int = 3

    def __post_init__(self) -> None:
        if self.top_k < 1 or self.candidate_k < self.top_k:
            raise InvariantError("need 1 <= top_k <= candidate_k")


@dataclass(frozen=True)
class Hit:
    record: ChunkRecord
    rank: int
    fused_score: float
    lexical_score: float | None = None
    lexical_rank: int | None = None
    vector_score: float | None = None
    vector_rank: int | None = None

    @property
    def key(self) -> str:
        return self.record.key

    def to_dict(self) -> dict[str, object]:
        return {
            "rank": self.rank,
            "key": self.key,
            "document_id": self.record.document_id,
            "language": self.record.language,
            "fused": round(self.fused_score, 5),
            "lexical": None
            if self.lexical_score is None
            else round(self.lexical_score, 4),
            "lexical_rank": self.lexical_rank,
            "vector": None
            if self.vector_score is None
            else round(self.vector_score, 4),
            "vector_rank": self.vector_rank,
        }


@dataclass(frozen=True)
class OutOfScopeEvidence:
    """What the probe may reveal: owner, document id and scores (no text)."""

    document_id: str
    owner_node: str
    lexical_score: float | None
    vector_score: float | None


@dataclass
class RetrievalResult:
    query: str
    node: str
    filters: SearchFilters
    hits: list[Hit] = field(default_factory=list)
    duplicates_dropped: list[tuple[str, str]] = field(
        default_factory=list
    )  # (dropped, kept)
    candidates: int = 0
    out_of_scope: list[OutOfScopeEvidence] = field(default_factory=list)
    timings_s: dict[str, float] = field(default_factory=dict)

    @property
    def best_vector(self) -> float | None:
        scores = [h.vector_score for h in self.hits if h.vector_score is not None]
        return max(scores) if scores else None

    @property
    def best_lexical(self) -> float | None:
        scores = [h.lexical_score for h in self.hits if h.lexical_score is not None]
        return max(scores) if scores else None

    def document_ids(self) -> list[str]:
        out: list[str] = []
        for hit in self.hits:
            if hit.record.document_id not in out:
                out.append(hit.record.document_id)
        return out


class HybridRetriever:
    def __init__(
        self,
        store: ChunkStorePort,
        lexical: Bm25Index,
        vectors: VectorIndexPort | None = None,
        embedder: EmbeddingPort | None = None,
        scope: ScopePort | None = None,
        config: RetrievalConfig | None = None,
    ) -> None:
        if (vectors is None) != (embedder is None):
            raise InvariantError("vector index and embedder must be given together")
        self.store = store
        self.lexical = lexical
        self.vectors = vectors
        self.embedder = embedder
        self.scope = scope
        self.config = config or RetrievalConfig()

    @property
    def mode(self) -> str:
        return "hybrid" if self.vectors is not None else "lexical"

    # -- candidate selection -------------------------------------------------
    def _partition(
        self, node: str | None, filters: SearchFilters
    ) -> tuple[list[str], list[str]]:
        admitted = [r for r in self.store.all() if filters.admits(r)]
        if node is None or self.scope is None:
            return [r.key for r in admitted], []
        if not self.scope.exists(node):
            raise NotFoundError(f"unknown node {node}")
        visible = self.scope.visible_documents(node)
        inside = [r.key for r in admitted if r.document_id in visible]
        outside = [r.key for r in admitted if r.document_id not in visible]
        return inside, outside

    def _rank(
        self, query: str, qvec: list[float] | None, keys: list[str], limit: int
    ) -> list[Hit]:
        if not keys:
            return []
        lex = self.lexical.search(query, limit, allowed=keys)
        rankings: dict[str, list[str]] = {"lexical": [k for k, _ in lex]}
        vec: list[tuple[str, float]] = []
        if qvec is not None and self.vectors is not None:
            vec = self.vectors.search(qvec, limit, allowed=keys)
            rankings["vector"] = [k for k, _ in vec]
        fused = reciprocal_rank_fusion(
            rankings,
            k=self.config.rrf_k,
            weights={
                "lexical": self.config.lexical_weight,
                "vector": self.config.vector_weight,
            },
        )
        lex_pos = {k: (i + 1, s) for i, (k, s) in enumerate(lex)}
        vec_pos = {k: (i + 1, s) for i, (k, s) in enumerate(vec)}
        hits: list[Hit] = []
        for i, (key, score) in enumerate(fused):
            lr = lex_pos.get(key)
            vr = vec_pos.get(key)
            hits.append(
                Hit(
                    self.store.get(key),
                    i + 1,
                    score,
                    lexical_score=lr[1] if lr else None,
                    lexical_rank=lr[0] if lr else None,
                    vector_score=vr[1] if vr else None,
                    vector_rank=vr[0] if vr else None,
                )
            )
        return hits

    def _collapse(self, hits: list[Hit]) -> tuple[list[Hit], list[tuple[str, str]]]:
        kept: list[Hit] = []
        dropped: list[tuple[str, str]] = []
        kept_shingles: list[frozenset[str]] = []
        for hit in hits:
            rec = hit.record
            group = rec.duplicate_of or rec.key
            sh = shingles(rec.text)
            twin: str | None = None
            for other, osh in zip(kept, kept_shingles):
                o = other.record
                if o.language != rec.language:
                    continue  # FA/EN pair is never a duplicate (Phase 5 rule)
                if (o.duplicate_of or o.key) == group or (
                    o.content_hash and o.content_hash == rec.content_hash
                ):
                    twin = o.key
                    break
                if (
                    sh
                    and osh
                    and jaccard(sh, osh) >= self.config.near_duplicate_threshold
                ):
                    twin = o.key
                    break
            if twin is not None:
                dropped.append((rec.key, twin))
                continue
            kept.append(hit)
            kept_shingles.append(sh)
        return kept, dropped

    # -- public API ------------------------------------------------------------
    def retrieve(
        self,
        query: str,
        node: str | None = None,
        filters: SearchFilters | None = None,
        *,
        top_k: int | None = None,
        probe_outside: bool = True,
    ) -> RetrievalResult:
        if not query.strip():
            raise InvariantError("query text is required")
        filters = filters or SearchFilters()
        top_k = top_k or self.config.top_k
        result = RetrievalResult(query, node or "", filters)
        t0 = time.perf_counter()
        inside, outside = self._partition(node, filters)
        result.candidates = len(inside)
        qvec: list[float] | None = None
        if self.embedder is not None:
            t = time.perf_counter()
            qvec = self.embedder.embed([query])[0]
            result.timings_s["embed_query"] = time.perf_counter() - t
        t = time.perf_counter()
        ranked = self._rank(query, qvec, inside, self.config.candidate_k)
        kept, dropped = self._collapse(ranked)
        result.hits = [
            Hit(
                h.record,
                i + 1,
                h.fused_score,
                h.lexical_score,
                h.lexical_rank,
                h.vector_score,
                h.vector_rank,
            )
            for i, h in enumerate(kept[:top_k])
        ]
        result.duplicates_dropped = dropped
        if probe_outside and outside:
            probe = self._rank(query, qvec, outside, self.config.candidate_k)[
                : self.config.probe_k
            ]
            result.out_of_scope = [
                OutOfScopeEvidence(
                    h.record.document_id,
                    h.record.owner_node,
                    h.lexical_score,
                    h.vector_score,
                )
                for h in probe
            ]
        result.timings_s["search"] = time.perf_counter() - t
        result.timings_s["total"] = time.perf_counter() - t0
        return result
