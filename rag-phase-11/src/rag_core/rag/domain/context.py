"""Context assembly under a token budget, with a source reference per block.

* Order: documents in the order of their best hit; inside one document,
  chunks in reading order (Phase 4 ``order``), so adjacent clauses read
  naturally.
* Budget: blocks are added while the estimated tokens (Phase 4 heuristic,
  2 chars ≈ 1 token, deliberately pessimistic) fit; a block larger than
  ``max_block_tokens`` is cut at a word boundary and marked "[…]".
* Labels: ``[AR-HR-005 §12]``. If one label occurs in both languages the
  label gets a language suffix (``§12/en``) so every citation is unique.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rag_core.ingestion.application.chunking import estimate_tokens
from rag_core.rag.domain.records import SourceRef
from rag_core.rag.domain.retriever import Hit
from rag_core.shared_kernel.errors import InvariantError

TRUNCATION_MARK = " […]"


@dataclass(frozen=True)
class ContextBlock:
    label: str
    hit: Hit
    text: str
    tokens: int
    truncated: bool = False

    @property
    def source(self) -> SourceRef:
        return self.hit.record.source

    def render(self) -> str:
        return f"[{self.label}] {self.source.describe()}\n{self.text}"


@dataclass
class AssembledContext:
    blocks: list[ContextBlock] = field(default_factory=list)
    budget_tokens: int = 0
    dropped: list[str] = field(default_factory=list)

    @property
    def token_count(self) -> int:
        return sum(b.tokens for b in self.blocks)

    @property
    def text(self) -> str:
        return "\n\n".join(b.render() for b in self.blocks)

    @property
    def labels(self) -> list[str]:
        return [b.label for b in self.blocks]

    def block(self, label: str) -> ContextBlock | None:
        for b in self.blocks:
            if b.label == label:
                return b
        return None

    def is_empty(self) -> bool:
        return not self.blocks


def _cut(text: str, max_tokens: int) -> str:
    if estimate_tokens(text) <= max_tokens:
        return text
    limit = max(1, max_tokens * 2 - len(TRUNCATION_MARK))
    head = text[:limit]
    space = head.rfind(" ")
    if space > limit * 0.6:
        head = head[:space]
    return head.rstrip() + TRUNCATION_MARK


class ContextAssembler:
    def __init__(self, budget_tokens: int = 3500, max_block_tokens: int = 900) -> None:
        if budget_tokens < 50 or max_block_tokens < 20:
            raise InvariantError("budget too small")
        self.budget_tokens = budget_tokens
        self.max_block_tokens = max_block_tokens

    @staticmethod
    def _labels(hits: list[Hit]) -> dict[str, str]:
        base: dict[str, set[str]] = {}
        for h in hits:
            base.setdefault(h.record.source.label, set()).add(h.record.language)
        out: dict[str, str] = {}
        for h in hits:
            label = h.record.source.label
            out[h.key] = (
                f"{label}/{h.record.language}" if len(base[label]) > 1 else label
            )
        return out

    def assemble(self, hits: list[Hit]) -> AssembledContext:
        ctx = AssembledContext(budget_tokens=self.budget_tokens)
        if not hits:
            return ctx
        labels = self._labels(hits)
        doc_rank: dict[tuple[str, str], int] = {}
        for h in hits:
            doc_rank.setdefault((h.record.document_id, h.record.language), h.rank)
        # Choose by relevance first (so the budget keeps the best hits) ...
        chosen: list[ContextBlock] = []
        used = 0
        for h in sorted(hits, key=lambda x: x.rank):
            text = _cut(h.record.text, self.max_block_tokens)
            tokens = (
                estimate_tokens(text) + estimate_tokens(h.record.source.describe()) + 4
            )
            if used + tokens > self.budget_tokens:
                ctx.dropped.append(h.key)
                continue
            used += tokens
            chosen.append(
                ContextBlock(labels[h.key], h, text, tokens, text != h.record.text)
            )
        # ... then order for reading: document by best rank, chunks by order.
        chosen.sort(
            key=lambda b: (
                doc_rank[(b.hit.record.document_id, b.hit.record.language)],
                b.hit.record.order,
            )
        )
        ctx.blocks = chosen
        return ctx
