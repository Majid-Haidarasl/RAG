# Phase 5 — Versioning, chunk lifecycle and duplicate detection

Status: implemented in `rag-core 0.5.0`. Context: **Knowledge Management**.
Pure standard library; no new dependencies.

| Concern | Code |
|---|---|
| Lifecycle (aggregate) | `src/rag_core/knowledge/domain/model.py` |
| Fingerprints (normalize, shingles, MinHash, LSH) | `src/rag_core/knowledge/domain/fingerprint.py` |
| Duplicate / near-duplicate / overlap rules | `src/rag_core/knowledge/domain/dedup.py` |
| Ingestion → lifecycle mapping | `src/rag_core/knowledge/application/lifecycle.py` |
| Corpus run + PHASE 5 SUMMARY | `scripts/run_corpus_dedup.py` |
| Tests | `tests/unit/knowledge/test_version_lifecycle.py`, `test_chunk_lifecycle.py`, `test_fingerprint.py`, `test_dedup.py`, `test_lifecycle_service.py` |

## 1. Version lifecycle

```
             stage_draft               activate
   (none) ───────────────► DRAFT ─────────────────► ACTIVE ──(next activate)──► SUPERSEDED ──archive──► ARCHIVED
                              │                        │
                              └──discard_draft──► ARCHIVED   └──withdraw──► ARCHIVED
```

* `KnowledgeItem` is the aggregate root, **one per document id** (e.g. `AR-HW-012`).
  FA and EN are *language versions of the same item*, each with an independent lifecycle.
* `KnowledgeVersion` carries `tag` (`major.minor`), `language`, `status`,
  `file_sha256`, `effective_from`, `effective_to`, `supersedes`.
* Compatibility with Phase 3: `VersionStatus.INACTIVE` is an enum alias of
  `SUPERSEDED`; `add_version()` still creates **and activates** in one step
  (it is `stage_draft()` + `activate()`).

### Invariants (enforced in the aggregate; per language)

| # | Rule | Error |
|---|---|---|
| V1 | At most one ACTIVE version | structural (activate supersedes the previous one) |
| V2 | At most one DRAFT version | `draft already exists` |
| V3 | Tags strictly increase | `must be greater than` |
| V4 | A new version's `supersedes` = the version that was active when the draft was staged (or the latest tag) | structural |
| V5 | Activation date ≥ `effective_from` of the version it supersedes; the superseded version gets `effective_to` = new `effective_from` | `cannot precede` |
| V6 | Only a DRAFT can be activated | `only a draft` |
| V7 | ACTIVE cannot be archived directly (use `withdraw` or supersede) | `cannot be archived` |
| V8 | A version needs ≥ 1 chunk, unique chunk ids, non-decreasing order | Phase 3 rules |

`supersedes_chain(language)` walks from the newest version back to the first, e.g. `1.2 ← 1.1 ← 1.0`.

## 2. Chunk lifecycle (tied to the version)

| Chunk status | When | Retrievable? |
|---|---|---|
| `active` | version is ACTIVE (or a fresh DRAFT's own chunks) | yes (if version ACTIVE) |
| `stale` | the ACTIVE version has a DRAFT successor waiting | yes, until the draft is activated |
| `retired` | version is SUPERSEDED / ARCHIVED, or a discarded draft | no |

`KnowledgeChunk` stays a frozen value object; status changes return a copy
(`with_status`). Every chunk has two hashes: `content_hash` (exact bytes) and
`normalized_hash` (canonical form, §4.1). `qualified_chunk_id` gives a globally
unique id: `AR-HW-012@1.1/fa#c0007`.

Rule C1: all chunks of a SUPERSEDED/ARCHIVED version are RETIRED.
Rule C2: STALE exists only while a DRAFT exists. `discard_draft` returns them to ACTIVE.

## 3. Re-ingest by SHA-256

`KnowledgeItem.reingest(language, file_sha256, chunks)`:

1. Same SHA-256 as the active version → **no new version**, event `ReingestSkippedUnchanged`, returns `None`.
2. Different SHA-256 → next minor tag (`1.0 → 1.1`), activated immediately, previous version SUPERSEDED, its chunks RETIRED.

`KnowledgeLifecycleService.ingest(IngestedDocument)` maps Phase 4 output onto
the aggregate: first file of a document → `registered`; first file of the other
language → `added_language` (same catalog tag, e.g. both 1.0); later files →
`unchanged` or `new_version`.

### Domain events

`KnowledgeItemRegistered`, `KnowledgeVersionDrafted`, `ChunksMarkedStale`,
`KnowledgeVersionSuperseded`, `ChunksRetired`, `KnowledgeVersionActivated`,
`KnowledgeVersionArchived` (reason: draft discarded / withdrawn),
`ReingestSkippedUnchanged`. Payload: `document_id`, `version`, `language` (+ `count`, `by`, `reason`).

## 4. Duplicate detection

### 4.1 Normalization for hashing

NFKC → Arabic ي/ى→ی, ك→ک → Persian/Arabic-Indic digits → Latin → lowercase →
remove ZWNJ/ZWJ/bidi marks/tatweel and Arabic diacritics → punctuation and
symbols become spaces → tokens → joined without spaces. So `می‌رود` = `می رود`
= `میرود`, `۱۲۰۰` = `1200`, and DOCX vs PDF line breaks do not matter. A real
change (`۱۲۰۰` → `۱۳۰۰`) changes the hash.

### 4.2 Rules and thresholds

| Rule | Method | Threshold | Why |
|---|---|---|---|
| Exact | sha256 of the normalized text | normalized length ≥ **30** chars | shorter texts are headings like "Purpose and scope", repeated by design |
| Near | word **3-shingles**; MinHash **64** permutations, `(a·x+b) mod (2^61−1)`, blake2b-64 base hash, fixed seed 1405; LSH **16 bands × 4 rows**; **verified with exact Jaccard** | Jaccard ≥ **0.80**, ≥ **8** shingles | the LSH S-curve is at ≈ (1/16)^(1/4) ≈ 0.50, so pairs at 0.80 collide with probability 1−(1−0.8⁴)¹⁶ ≈ 0.9998 |
| Overlap / containment | inverted shingle index; shingles present in more than max(5, 25 % of source files) are **boilerplate** and ignored for candidate generation | containment of the smaller side ≥ **0.60**, not exact/near | finds a paragraph copied into a longer chunk |

Exclusions, applied to every rule:

* **Same source file**: never compared. The chunker overlaps neighbouring chunks by 200 characters on purpose.
* **Bilingual pair**: same document id and different language. It is a translation pair, never a duplicate. Derived renditions have no language folder, so their language is guessed by script (Arabic-script vs Latin letter share ≥ 50 %). The report counts *would-flag* exclusions (`bilingual_pairs_excluded`) separately from mere candidates (`bilingual_candidates_seen`). The realistic risk is a numbers-only table: Persian digits normalize to Latin, so FA and EN tables hash identically. The unit test `test_bilingual_numeric_table_is_excluded_even_when_hashes_match` covers this.

Every finding has a **scope**:

* `rendition`: same document and language in another file format (DOCX vs the exported PDF/DOC). Expected; it confirms the export.
* `cross_document`: different documents. This is a real content-reuse finding.

LSH quality is measured on every run. The overlap index also computes exact
Jaccard for its candidates; `lsh_recall = near_pairs / reference_near_pairs`.

## 5. Corpus results (box, Debian 13, Python 3.13.5; 2026-11-11)

| Metric | Value |
|---|---|
| Files | 52 official (26 FA + 26 EN) + 8 derived |
| Knowledge items / bilingual items | 26 / 26 |
| Versions | 53 (52 active, 1 superseded) |
| Chunks | 1219 active, 0 stale, 23 retired |
| Update simulation (AR-HW-012 FA) | unchanged re-ingest → `unchanged`; modified copy → `1.1`, chain `1.1 ← 1.0`, 23 chunks retired, EN stays 1.0 |
| Chunk records | 1402 |
| Exact groups | 51 (22 rendition, 29 cross-document) |
| Near-dup pairs | 7 (1 rendition, 6 cross-document) |
| Overlap pairs | 404 (58 rendition, 346 cross-document) |
| Bilingual exclusions | 0 would-flag; 223 bilingual candidates skipped |
| LSH candidates / recall | 988 / 1.000 |
| Document level | 2 exact rendition groups (DOC ↔ DOCX), 3 near renditions (PDF/DOC ↔ DOCX, J ≈ 0.97) |
| Time | ingest ≈ 6.5 s, lifecycle 0.2 s, chunk dedup ≈ 2.2 s, document dedup ≈ 1.9 s |

### Findings

* **F5-1 — Persian PDF text is garbled.** The three Persian PDF renditions
  (AR-FIN-008, AR-HR-005, AR-SW-022 FA) extract with pdfplumber as `(cid:NN)`
  glyph ids in visual order (LibreOffice embeds Noto Naskh as Type 3 /
  contextual-form glyphs). Phase 4 counted them as "success" because parsing
  did not fail. Dedup cannot match them to their DOCX (Jaccard ≈ 0.001).
  The summary now reports `garbled_pdf_text: 3`. `pdftotext` (poppler) returns
  Persian in logical order (with some split-glyph artifacts), so it is the
  candidate fix for a later phase. English PDFs are fine (J ≈ 0.97).
* **F5-2 — templated paragraphs across policies.** Seven governance documents
  (AR-BRD-003, AR-HR-004…007, AR-ORG-001, AR-ORG-002) repeat the same
  "کنترل مرز / کنترل شاهد / کنترل اجرا" (FA) and "Output and responsibility /
  apparent conflict" (EN) paragraphs word for word. These are the 29
  cross-document exact groups and most cross-document overlaps. Retrieval
  should de-duplicate them at answer time (Phase 6+), or the corpus generator
  should vary them.
* **F5-3 — header blocks.** 88 overlap pairs involve `c0001` header chunks
  (document ID, class, owner, version lines) of same-family documents. They
  are reported, not suppressed. Lowering `boilerplate_source_fraction` would
  hide them if desired.

## 6. Decisions

1. Dedup lives in the Knowledge domain as pure functions over `TextRecord`s;
   the ingestion context only supplies text. There is no persistence yet (in-memory repository).
2. Thresholds are configuration (`DedupConfig`), not constants spread in code.
3. Near-dup candidates are always verified with exact Jaccard: no false positives from MinHash.
4. Derived renditions take part in dedup only; they never create knowledge versions.
5. Dates: the corpus is effective from 2024-10-01 (catalog 1403-07); the simulated update from 2026-11-11 (۱۴۰۵/۰۸/۲۰).
