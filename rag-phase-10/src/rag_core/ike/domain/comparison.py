"""Issue-knowledge comparison: what an item cites vs what its scope retrieves.

For one sub-issue (or issue) asked from its owner node:

``cited``          related documents in the issue registry;
``retrieved``      documents of the top hits, in rank order (Phase 8 retriever, node-scoped);
``covered``        cited and retrieved;
``suggested``      retrieved but not cited (candidate knowledge the team owner may add);
``missed``         cited, visible from the owner node, but not retrieved;
``outside_scope``  cited but not visible from the owner node (needs escalation or transfer);
``evidence``       best in-scope score passes the Phase 8 evidence floor.

``cited_recall`` = covered / visible cited documents (``None`` if nothing cited is visible).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class KnowledgeHit:
    document_id: str
    rank: int
    key: str = ""
    language: str = ""
    lexical: float | None = None
    vector: float | None = None


@dataclass(frozen=True)
class KnowledgeSearchResult:
    query: str
    node: str
    hits: tuple[KnowledgeHit, ...] = ()
    visible_documents: frozenset[str] = field(default_factory=frozenset)
    outside_owners: tuple[str, ...] = ()
    mode: str = "lexical"
    seconds: float = 0.0

    def documents(self) -> list[str]:
        out: list[str] = []
        for h in self.hits:
            if h.document_id not in out:
                out.append(h.document_id)
        return out

    @property
    def best_lexical(self) -> float | None:
        scores = [h.lexical for h in self.hits if h.lexical is not None]
        return max(scores) if scores else None

    @property
    def best_vector(self) -> float | None:
        scores = [h.vector for h in self.hits if h.vector is not None]
        return max(scores) if scores else None


@dataclass(frozen=True)
class IssueKnowledgeComparison:
    item_id: str
    node: str
    cited: tuple[str, ...]
    retrieved: tuple[str, ...]
    covered: tuple[str, ...]
    suggested: tuple[str, ...]
    missed: tuple[str, ...]
    outside_scope: tuple[str, ...]
    outside_owners: tuple[str, ...]
    evidence: bool
    mode: str = "lexical"
    best_lexical: float | None = None
    best_vector: float | None = None
    seconds: float = 0.0

    @property
    def cited_recall(self) -> float | None:
        visible = len(self.cited) - len(self.outside_scope)
        return None if visible <= 0 else round(len(self.covered) / visible, 4)

    def rank_of(self, document_id: str) -> int | None:
        try:
            return self.retrieved.index(document_id) + 1
        except ValueError:
            return None

    def to_dict(self) -> dict[str, object]:
        return {
            "item_id": self.item_id,
            "node": self.node,
            "mode": self.mode,
            "cited": list(self.cited),
            "retrieved": list(self.retrieved),
            "covered": list(self.covered),
            "suggested": list(self.suggested),
            "missed": list(self.missed),
            "outside_scope": list(self.outside_scope),
            "outside_owners": list(self.outside_owners),
            "evidence": self.evidence,
            "cited_recall": self.cited_recall,
            "best_lexical": None
            if self.best_lexical is None
            else round(self.best_lexical, 4),
            "best_vector": None
            if self.best_vector is None
            else round(self.best_vector, 4),
            "seconds": round(self.seconds, 4),
        }


def compare_knowledge(
    item_id: str,
    cited: tuple[str, ...],
    result: KnowledgeSearchResult,
    *,
    min_lexical: float = 3.0,
    min_vector: float = 0.45,
) -> IssueKnowledgeComparison:
    cited = tuple(dict.fromkeys(cited))
    retrieved = tuple(result.documents())
    visible = result.visible_documents
    outside = tuple(d for d in cited if visible and d not in visible)
    covered = tuple(d for d in cited if d in retrieved)
    suggested = tuple(d for d in retrieved if d not in cited)
    missed = tuple(d for d in cited if d not in retrieved and d not in outside)
    if result.best_vector is not None:
        evidence = result.best_vector >= min_vector
    else:
        evidence = (
            result.best_lexical is not None and result.best_lexical >= min_lexical
        )
    return IssueKnowledgeComparison(
        item_id,
        result.node,
        cited,
        retrieved,
        covered,
        suggested,
        missed,
        outside,
        tuple(result.outside_owners),
        evidence,
        result.mode,
        result.best_lexical,
        result.best_vector,
        result.seconds,
    )
