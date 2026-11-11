# Phase 5 — Versioning, chunk lifecycle and duplicate detection

Status: implemented in `rag-core 0.5.0`; PDF fix and document-level char mode in `0.5.1`. Context: **Knowledge Management**.
Pure standard library; no new dependencies.

| Concern | Code |
|---|---|
| Lifecycle (aggregate) | `src/rag_core/knowledge/domain/model.py` |
| Fingerprints (normalize, word/char shingles, MinHash, LSH) | `src/rag_core/knowledge/domain/fingerprint.py` |
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

## 5. Corpus results (box, Debian 13, Python 3.13.5, poppler 25.03; 0.5.1, 2026-11-12)

Two passes run per corpus:

* **chunk level**: word 3-shingles, MinHash/LSH (§4.2);
* **document level** (rendition matching): whitespace-insensitive **char 5-grams** of the
  normalized text, all pairs compared exactly (`exhaustive=True`, 59 documents),
  near ≥ 0.80, containment ≥ **0.80**. Char grams ignore the spurious spaces
  in Arabic-script PDF text. Containment is raised to 0.80 because, at 0.60,
  English documents of one family overlapped by shared vocabulary alone
  (0.60–0.63), while renditions score ≥ 0.86.

| Metric | 0.5.0 | 0.5.1 |
|---|---|---|
| Tests | 129 | 149 |
| Ingest chunks (all 60 files) | 1402 | 1356 (PDF paragraphs now from poppler) |
| PDF engine | pdfplumber | pdftotext ×6 |
| PDF text quality | not checked | ok 2, fragmented 3, empty 1 (scan), garbled 0 |
| Knowledge items / versions | 26 / 53 (52 active, 1 superseded) | same |
| Chunks active / retired | 1219 / 23 | same |
| Update simulation AR-HW-012 FA | unchanged → no-op; changed → 1.1, 23 retired | same |
| Exact groups (chunk) | 51 (22 rendition, 29 cross-doc) | 52 (23 / 29) |
| Near pairs (chunk) | 7 (1 / 6) | 26 (14 / 12) |
| Overlap pairs (chunk) | 404 (58 / 346) | 433 (69 / 364) |
| Bilingual would-flag / candidates skipped | 0 / 223 | 0 / 222 |
| LSH recall | 1.000 | 1.000 |
| Doc-level near (renditions) | 3 (EN only) | **7**: all DOC/PDF renditions incl. 3 Persian PDFs (J 0.86 FIN-008, 0.97 HR-005, 0.96 SW-022) |
| Doc-level cross-document | 0 | 0 |
| `garbled_pdf_text` | 3 | **0** |
| Time (ingest / chunk dedup / doc dedup) | 6.5 / 2.2 / 1.9 s | 6.4 / 1.9 / 2.6 s |

### Findings

* **F5-1: Persian PDF text was garbled. Fixed in 0.5.1.** pdfplumber returned
  `(cid:NN)` placeholders in visual order and Phase 4 counted the files as success.
  Now poppler `pdftotext -bbox` is the primary engine, with RTL line rebuilding,
  and a quality check rejects garbled text as a failure. The three Persian PDFs
  are readable and in logical order but marked `fragmented` (some two-letter
  splits remain, e.g. `مرخ صی`). Details: `pdf-text-extraction.md`.
* **F5-2: templated paragraphs across policies.** Seven governance documents
  (AR-BRD-003, AR-HR-004…007, AR-ORG-001, AR-ORG-002) repeat the same
  "کنترل مرز / کنترل شاهد / کنترل اجرا" (FA) and "Output and responsibility /
  apparent conflict" (EN) paragraphs word for word. These are the 29
  cross-document exact groups and most cross-document overlaps. Retrieval
  should de-duplicate them at answer time (Phase 6+), or the corpus generator
  should vary them.
* **F5-3: header blocks.** Overlap pairs on `c0001` header chunks (document
  ID, class, owner, version lines) of same-family documents are reported, not
  suppressed.

## 6. Decisions

1. Dedup lives in the Knowledge domain as pure functions over `TextRecord`s;
   the ingestion context only supplies text. There is no persistence yet (in-memory repository).
2. Thresholds are configuration (`DedupConfig`), not constants spread in code.
3. Near-dup candidates are always verified with exact Jaccard: no false positives from MinHash.
4. Derived renditions take part in dedup only; they never create knowledge versions.
5. Dates: the corpus is effective from 2024-10-01 (catalog 1403-07); the simulated update from 2026-11-11 (۱۴۰۵/۰۸/۲۰).
