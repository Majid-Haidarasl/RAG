# Phase 4 — Structure-aware chunking

Status: v1.0. Date: 10 November 2026.
Implementation: `rag_core.ingestion.application.chunking`. Target embedding model: **bge-m3** (Phase 2), `num_ctx` 8192, embedding dim 1024.

## 1. Goal

Chunks should be retrievable units, not arbitrary windows. They must:

- respect headings, numbered clauses and tables;
- stay well under the 8192-token embedding window;
- keep a short overlap when a long paragraph has to be split;
- carry the heading path and source anchors of §`source-reference-model.md`.

## 2. Size budget

No Hugging Face tokenizer is added to the core (offline, no extra model files). Size is enforced with two caps:

| Cap | Default | Rationale |
|---|---|---|
| `max_chars` | 1600 | Comfortable for a bilingual technical paragraph plus its heading |
| `max_tokens` (heuristic) | 512 | Hard stop. Estimate is `max(len(text)//2, word_count)` — a conservative upper bound for XLM-RoBERTa/Persian subwords |
| `overlap_chars` | 200 | Only when a single block is longer than the cap |

512 estimated tokens is far below 8192, so a later query + prefix will still fit in `num_ctx`. The knobs are constants in `chunking.py` and can be retuned when a real tokenizer is added.

## 3. Rules

1. **Headings** (Word `Heading N`, `عنوان N`, or outline level) start a new section. The heading text is kept at the front of the next prose chunk. The heading path is copied onto every chunk in that section.
2. **Paragraphs and list items** under the same heading are packed together until a cap would be exceeded, then a new chunk starts (no overlap between packed blocks).
3. **Tables** are atomic if they fit. If not, they are split by **rows**, with the header row repeated in each piece. Cells are not broken mid-text.
4. A **single oversize paragraph** is split on a nearby newline, space, `،`, or `.`, with `overlap_chars` of shared text.
5. Empty paragraphs are dropped. Running headers/footers are not parsed.

## 4. Identifier

`chunk_id` is `{document_id}#c{order:04d}`, e.g. `AR-HW-012#c0003`. Order is 1-based inside one file (one language version). The FA and EN files of the same id produce two independent sequences.

## 5. Out of scope

- Token-accurate splitting with the bge-m3 tokenizer.
- Semantic / embedding-based chunk boundaries (needs the model; unit tests must stay offline).
- Near-duplicate merging (Phase 5+).

## Note — PDF text source changed in 0.5.1

PDF paragraphs now come from poppler `pdftotext -bbox` with RTL line
reconstruction (one paragraph per vertical gap), not from pdfplumber page text.
Chunking rules are unchanged, but PDF chunk counts changed (ingest total 1402 →
1356). Garbled text is rejected before chunking. See
`docs/phase-05/pdf-text-extraction.md`.
