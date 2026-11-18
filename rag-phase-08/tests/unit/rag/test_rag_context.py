"""Context assembly: budget, order, labels, source references."""

import pytest

from rag_core.ingestion.application.chunking import estimate_tokens
from rag_core.rag.domain.context import TRUNCATION_MARK, ContextAssembler
from rag_core.rag.domain.retriever import Hit
from rag_core.shared_kernel.errors import InvariantError
from tests.fixtures.rag.fakes import rec

pytestmark = [pytest.mark.rag, pytest.mark.retrieval]


def hits(*records):  # noqa: ANN002, ANN201
    return [Hit(r, i + 1, 1.0 / (i + 1)) for i, r in enumerate(records)]


def test_empty_hits_give_empty_context() -> None:
    ctx = ContextAssembler().assemble([])
    assert ctx.is_empty() and ctx.text == "" and ctx.token_count == 0


def test_block_header_carries_label_version_and_anchor() -> None:
    ctx = ContextAssembler().assemble(hits(rec("AR-HR-005", 12, "مرخصی ساعتی ۴ ساعت", paragraph=40, heading="۵. مرخصی")))
    first = ctx.text.splitlines()[0]
    assert first.startswith("[AR-HR-005 §12] AR-HR-005 v1.0 (fa)")
    assert "¶40" in first and "۵. مرخصی" in first
    assert ctx.labels == ["AR-HR-005 §12"]


def test_language_suffix_only_when_label_collides() -> None:
    ctx = ContextAssembler().assemble(hits(
        rec("AR-ISS-024", 5, "فارسی"), rec("AR-ISS-024", 5, "english", lang="en"), rec("AR-SW-022", 3, "sla")))
    assert set(ctx.labels) == {"AR-ISS-024 §5/fa", "AR-ISS-024 §5/en", "AR-SW-022 §3"}


def test_reading_order_groups_document_chunks() -> None:
    ctx = ContextAssembler().assemble(hits(
        rec("AR-HR-005", 9, "b"), rec("AR-SW-022", 1, "x"), rec("AR-HR-005", 2, "a")))
    assert ctx.labels == ["AR-HR-005 §2", "AR-HR-005 §9", "AR-SW-022 §1"]


def test_budget_keeps_best_ranked_blocks() -> None:
    long_text = "کلمه " * 150  # ~375 tokens with the 2-char heuristic
    ctx = ContextAssembler(budget_tokens=500, max_block_tokens=450).assemble(hits(
        rec("AR-A-001", 1, long_text), rec("AR-B-002", 1, long_text), rec("AR-C-003", 1, "short")))
    assert "AR-A-001 §1" in ctx.labels and "AR-B-002 §1" not in ctx.labels
    assert "AR-C-003 §1" in ctx.labels, "a smaller later block still fits"
    assert ctx.dropped == ["AR-B-002@1.0/fa#c0001"]
    assert ctx.token_count <= 500


def test_long_block_truncated_at_word_boundary() -> None:
    text = " ".join(f"word{i}" for i in range(400))
    ctx = ContextAssembler(budget_tokens=2000, max_block_tokens=100).assemble(hits(rec("AR-A-001", 1, text, lang="en")))
    block = ctx.blocks[0]
    assert block.truncated and block.text.endswith(TRUNCATION_MARK)
    assert estimate_tokens(block.text) <= 100
    assert not block.text[: -len(TRUNCATION_MARK)].endswith("wor")


def test_block_lookup_and_source() -> None:
    ctx = ContextAssembler().assemble(hits(rec("AR-HR-005", 1, "x")))
    assert ctx.block("AR-HR-005 §1").source.document_id == "AR-HR-005"
    assert ctx.block("nope") is None


def test_assembler_validation() -> None:
    with pytest.raises(InvariantError):
        ContextAssembler(budget_tokens=10)
