# Phase 4 — Source reference model

Status: v1.0. Date: 10 November 2026.
This is the citation anchor that Phase 8 (fact validation and grounded answers) will use. It extends the Phase 3 `SourceReference` / `Citation` value objects with positional fields that a parser can actually fill.

## 1. Why anchors exist

A citation such as “AR-SW-022, section P1” is enough for a human, but a program that checks names and numbers against the source (Phase 8) needs a span: which paragraph or table cell, and which character range in the stored text.

## 2. Anchor fields

Implemented as `rag_core.ingestion.domain.model.SourceAnchor`:

| Field | DOCX / DOC | Text PDF | Meaning |
|---|---|---|---|
| `document_id` | yes | yes | Latin-digit id |
| `block_index` | yes | yes | Order of the block in the parsed body (0-based) |
| `paragraph_index` | yes (body paragraphs, including empty ones counted) | best-effort | Stable-ish paragraph number |
| `page` | usually omitted | 1-based page number | DOCX page breaks are not reliable without a layout engine |
| `char_start`, `char_end` | yes | yes | Offsets in the **normalized** block text, half-open `[start, end)` |
| `table_index` | yes when the block is a table | yes | 0-based table in the document or page |
| `row`, `column` | reserved for cell-level anchors | reserved | Filled when a chunk is a single cell (rare); row splits of a large table keep `table_index` and describe the row range in the chunk text |
| `heading_path` | yes | when headings were detected | e.g. `6. Capabilities > Web team` |

A `TextChunk` stores one or more anchors (a chunk may pack several short paragraphs under the same heading).

## 3. What the stored text is

Offsets apply to the text **after** Persian normalization (yeh/kaf, ZWNJ, identifier digits). The original file is still addressed by `file_sha256` on the metadata record, so a later auditor can reopen the raw bytes.

## 4. Limits (honest)

- DOCX: python-docx does not give a printed page number. Citations for Word files use heading path + paragraph/block + offsets, not a page.
- Tables: the default chunk is the whole table (or a header + a row group). Cell-level `row`/`column` can be added later without changing the metadata schema.
- Headers and footers are not ingested (they repeat and pollute retrieval).
- A scanned PDF has no trustworthy character offsets; the document is flagged `is_scanned` and left for LVM OCR.

## 5. Example

```json
{
  "document_id": "AR-SW-022",
  "block_index": 14,
  "paragraph_index": 18,
  "char_start": 0,
  "char_end": 86,
  "heading_path": "اولویت ۱ > زمان پاسخ"
}
```
