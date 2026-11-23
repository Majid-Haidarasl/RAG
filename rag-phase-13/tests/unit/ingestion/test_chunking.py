import pytest

from rag_core.ingestion.application.chunking import chunk_blocks, estimate_tokens
from rag_core.ingestion.domain.model import BlockKind, ContentBlock

pytestmark = pytest.mark.ingestion


def _p(index: int, text: str, heading: str = "H") -> ContentBlock:
    return ContentBlock(BlockKind.PARAGRAPH, text, index, heading_path=heading)


def test_heading_starts_a_new_chunk_and_is_kept_as_prefix() -> None:
    blocks = [
        ContentBlock(BlockKind.HEADING, "Leave", 0, heading_path="Leave", heading_level=1),
        _p(1, "Twenty-six days.", "Leave"),
        ContentBlock(BlockKind.HEADING, "Sick", 2, heading_path="Sick", heading_level=1),
        _p(3, "Five days.", "Sick"),
    ]
    chunks = chunk_blocks(blocks, document_id="AR-HR-005")
    assert len(chunks) == 2
    assert chunks[0].text.startswith("Leave")
    assert "Twenty-six" in chunks[0].text
    assert chunks[1].heading_path == "Sick"
    assert chunks[0].chunk_id == "AR-HR-005#c0001"


def test_table_is_atomic_when_it_fits() -> None:
    table = ContentBlock(
        BlockKind.TABLE,
        "A | B\n1 | 2",
        0,
        heading_path="T",
        table_index=0,
        cells=(("A", "B"), ("1", "2")),
    )
    chunks = chunk_blocks([table], document_id="AR-FIN-008")
    assert len(chunks) == 1
    assert chunks[0].kind == "table"
    assert chunks[0].anchors[0].table_index == 0


def test_oversized_paragraph_is_split_with_overlap() -> None:
    text = ("lorem ipsum dolor sit amet " * 80).strip()
    blocks = [_p(0, text, "X")]
    chunks = chunk_blocks(blocks, document_id="AR-ORG-001", max_chars=200, overlap_chars=40, max_tokens=10000)
    assert len(chunks) >= 2
    # Overlap: the start of chunk 2 should appear near the end of chunk 1.
    tail = chunks[0].text[-40:]
    assert any(word and word in chunks[1].text for word in tail.split()[:3])
    assert all(len(c.text) <= 200 for c in chunks)


def test_token_heuristic_is_positive() -> None:
    assert estimate_tokens("مرخصی استحقاقی سالانه") >= 4
