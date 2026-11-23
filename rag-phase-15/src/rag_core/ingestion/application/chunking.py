"""Structure-aware chunking for bge-m3 (max 8192 tokens, much smaller chunks).

No tokenizer dependency is added. Size is controlled by a character cap and a
heuristic token estimate. Defaults leave ample headroom under the 8192-token
model limit and keep a short overlap so a clause split across a boundary is
still retrievable.
"""

from __future__ import annotations

from rag_core.ingestion.domain.model import BlockKind, ContentBlock, SourceAnchor, TextChunk

# ~512 tokens of mixed Persian/English is well under bge-m3's 8192 window.
# A conservative 2.0 characters/token for Persian would make 1600 chars ≈ 800
# tokens; the token heuristic is the hard stop at MAX_TOKENS.
DEFAULT_MAX_CHARS = 1600
DEFAULT_OVERLAP_CHARS = 200
DEFAULT_MAX_TOKENS = 512


def estimate_tokens(text: str) -> int:
    """Cheap upper-bound token estimate without a real tokenizer.

    XLM-RoBERTa (bge-m3) often splits Persian into short subwords, so we
    treat every 2 characters as one token, with a floor of the whitespace
    word count.
    """
    if not text:
        return 0
    by_chars = max(1, (len(text) + 1) // 2)
    by_words = len(text.split())
    return max(by_chars, by_words)


def _fits(text: str, max_chars: int, max_tokens: int) -> bool:
    return len(text) <= max_chars and estimate_tokens(text) <= max_tokens


def _split_long(text: str, max_chars: int, overlap: int) -> list[tuple[int, int, str]]:
    """Split a single block by characters, preferring whitespace near the cap."""
    pieces: list[tuple[int, int, str]] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(n, start + max_chars)
        if end < n:
            window = text[start:end]
            cut = max(window.rfind("\n"), window.rfind(" "), window.rfind("،"), window.rfind("."))
            if cut >= max_chars // 2:
                end = start + cut + 1
        pieces.append((start, end, text[start:end].strip()))
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return [(a, b, t) for a, b, t in pieces if t]


def chunk_blocks(
    blocks: list[ContentBlock] | tuple[ContentBlock, ...],
    *,
    document_id: str,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> list[TextChunk]:
    """Pack blocks into chunks. Headings open a new section; tables stay atomic when they fit."""
    chunks: list[TextChunk] = []

    def emit(parts: list[tuple[ContentBlock, str, int, int]], *, kind: str, heading: str) -> None:
        if not parts:
            return
        text = "\n\n".join(p[1] for p in parts).strip()
        if not text:
            return
        anchors: list[SourceAnchor] = []
        for block, _text, start, end in parts:
            anchors.append(block.anchor(document_id, start, end))
        order = len(chunks) + 1
        chunk_id = f"{document_id}#c{order:04d}"
        chunks.append(
            TextChunk(
                chunk_id=chunk_id,
                order=order,
                text=text,
                heading_path=heading,
                anchors=tuple(anchors),
                kind=kind,
            )
        )

    buffer: list[tuple[ContentBlock, str, int, int]] = []
    buffer_heading = ""

    def buffer_text() -> str:
        return "\n\n".join(p[1] for p in buffer)

    def flush() -> None:
        nonlocal buffer
        emit(buffer, kind="prose", heading=buffer_heading)
        buffer = []

    def overflow_with(extra: str) -> bool:
        if not buffer:
            return False
        candidate = buffer_text() + "\n\n" + extra
        return not _fits(candidate, max_chars, max_tokens)

    for block in blocks:
        heading = block.heading_path or buffer_heading

        if block.kind is BlockKind.HEADING:
            flush()
            buffer_heading = block.heading_path or block.text
            # Keep the heading text at the start of the following chunk by
            # putting it in the buffer if it is short.
            if _fits(block.text, max_chars, max_tokens):
                buffer.append((block, block.text, 0, len(block.text)))
            continue

        if block.kind is BlockKind.TABLE:
            flush()
            buffer_heading = heading
            if _fits(block.text, max_chars, max_tokens):
                emit([(block, block.text, 0, len(block.text))], kind="table", heading=heading)
            else:
                # Split by rows, repeating the header row when present.
                rows = list(block.cells) if block.cells else [
                    tuple(line.split(" | ")) for line in block.text.splitlines()
                ]
                header = rows[0] if rows else tuple()
                current: list[tuple[str, ...]] = []

                def rows_text(rs: list[tuple[str, ...]]) -> str:
                    return "\n".join(" | ".join(r) for r in rs)

                for row in rows[1:] if header else rows:
                    candidate = [header, *current, row] if header else [*current, row]
                    if current and not _fits(rows_text(candidate), max_chars, max_tokens):
                        emit(
                            [(block, rows_text([header, *current] if header else current), 0, 0)],
                            kind="table",
                            heading=heading,
                        )
                        current = [row]
                    else:
                        current.append(row)
                if current or (header and not rows[1:]):
                    payload = [header, *current] if header else current
                    if header and not current:
                        payload = [header]
                    emit([(block, rows_text(payload), 0, 0)], kind="table", heading=heading)
            continue

        # Prose / list items / clauses: prefer to stay under the current heading.
        if buffer and heading != buffer_heading:
            flush()
            buffer_heading = heading

        if overflow_with(block.text):
            flush()
            buffer_heading = heading

        if _fits(block.text, max_chars, max_tokens):
            buffer.append((block, block.text, 0, len(block.text)))
            buffer_heading = heading
            continue

        flush()
        buffer_heading = heading
        pieces = _split_long(block.text, max_chars, overlap_chars)
        for start, end, piece in pieces:
            emit([(block, piece, start, end)], kind="prose", heading=heading)

    flush()
    return chunks
