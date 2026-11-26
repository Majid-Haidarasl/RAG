"""Embedding near-dedup with fake embedder/chat (no Ollama)."""

from __future__ import annotations

import pytest

from rag_core.knowledge.domain.embedding_dedup import (
    EmbeddingDedupConfig,
    EmbeddingNearDedup,
    TextPair,
)
from rag_core.shared_kernel.errors import InvariantError
from tests.fixtures.rag.fakes import FakeChat, FakeEmbedder


def test_same_threshold_marks_duplicate_without_llm() -> None:
    emb = FakeEmbedder()
    chat = FakeChat(reply='{"verdict": "different"}')
    svc = EmbeddingNearDedup(
        emb, chat, EmbeddingDedupConfig(same_threshold=0.5, borderline_low=0.3)
    )
    # Identical text → high cosine with bag-of-concepts FakeEmbedder.
    decision = svc.decide_pair(
        TextPair("a", "b", "controller RAM upgrade", "controller RAM upgrade")
    )
    assert decision.verdict == "same" and decision.source == "cosine"
    assert chat.calls == []


def test_below_borderline_is_different() -> None:
    emb = FakeEmbedder()
    svc = EmbeddingNearDedup(
        emb, None, EmbeddingDedupConfig(same_threshold=0.99, borderline_low=0.95)
    )
    decision = svc.decide_pair(
        TextPair("a", "b", "warehouse robotics", "board bylaws quorum")
    )
    assert decision.verdict == "different" and decision.source == "cosine"


def test_borderline_asks_llm() -> None:
    class FixedEmbedder:
        def embed(self, texts: list[str]) -> list[list[float]]:
            # Cosine of (1,0) and (0.8, 0.6) ≈ 0.8 — inside [0.7, 0.9).
            return [[1.0, 0.0], [0.8, 0.6]]

    chat = FakeChat(reply='{"verdict": "same"}')
    svc = EmbeddingNearDedup(
        FixedEmbedder(),
        chat,
        EmbeddingDedupConfig(same_threshold=0.9, borderline_low=0.7),
    )
    decision = svc.decide_pair(TextPair("a", "b", "left text", "right text"))
    assert decision.verdict == "same" and decision.source == "llm"
    assert len(chat.calls) == 1


def test_borderline_without_chat_raises() -> None:
    class FixedEmbedder:
        def embed(self, texts: list[str]) -> list[list[float]]:
            return [[1.0, 0.0], [0.8, 0.6]]

    svc = EmbeddingNearDedup(
        FixedEmbedder(),
        None,
        EmbeddingDedupConfig(same_threshold=0.9, borderline_low=0.7),
    )
    with pytest.raises(InvariantError, match="chat model"):
        svc.decide_pair(TextPair("a", "b", "left", "right"))


def test_bad_llm_verdict_raises() -> None:
    class FixedEmbedder:
        def embed(self, texts: list[str]) -> list[list[float]]:
            return [[1.0, 0.0], [0.8, 0.6]]

    chat = FakeChat(reply='{"verdict": "maybe"}')
    svc = EmbeddingNearDedup(
        FixedEmbedder(),
        chat,
        EmbeddingDedupConfig(same_threshold=0.9, borderline_low=0.7),
    )
    with pytest.raises(InvariantError, match="same|different"):
        svc.decide_pair(TextPair("a", "b", "left", "right"))


def test_config_rejects_bad_thresholds() -> None:
    with pytest.raises(InvariantError):
        EmbeddingDedupConfig(same_threshold=0.5, borderline_low=0.8)
