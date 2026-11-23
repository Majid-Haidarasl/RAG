"""Anti-corruption layer: Phase 8 ``HybridRetriever`` → IKE ``KnowledgeSearchPort``.

The only module of the IKE context that imports ``rag``. Only document ids,
ranks and scores leave the retriever; outside-scope evidence is reduced to
owner nodes (no text), as in Phase 8.
"""

from __future__ import annotations

import time

from rag_core.ike.domain.comparison import KnowledgeHit, KnowledgeSearchResult
from rag_core.rag.domain.ports import ScopePort
from rag_core.rag.domain.retriever import HybridRetriever


class RetrieverKnowledgeSearch:
    def __init__(self, retriever: HybridRetriever, scope: ScopePort | None = None) -> None:
        self.retriever = retriever
        self.scope = scope if scope is not None else retriever.scope

    def search(self, query: str, node: str, top_k: int) -> KnowledgeSearchResult:
        t0 = time.perf_counter()
        res = self.retriever.retrieve(query, node, top_k=top_k)
        hits = tuple(
            KnowledgeHit(h.record.document_id, h.rank, h.key, h.record.language, h.lexical_score, h.vector_score)
            for h in res.hits
        )
        visible = self.scope.visible_documents(node) if self.scope is not None else frozenset()
        owners = tuple(sorted({e.owner_node for e in res.out_of_scope if e.owner_node}))
        return KnowledgeSearchResult(query, node, hits, frozenset(visible), owners, self.retriever.mode,
                                     time.perf_counter() - t0)
