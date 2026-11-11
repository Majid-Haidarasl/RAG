# Phase 4 — Knowledge metadata schema

Status: v1.0. Date: 10 November 2026 (19 Aban 1405).
Machine-readable copy: `schemas/knowledge-metadata.json` (JSON Schema 2020-12).
The record is attached to every ingested file and later becomes the `MetadataRecord` of a `KnowledgeItem` (Phase 3 / glossary term 31).

## 1. Purpose

Ingestion must record, for each file:

- a stable document id with **Latin digits**;
- the language and the bilingual counterpart;
- the owning organizational node (and any additional official owners);
- document type, version, approval status and dates (Jalali and Gregorian);
- a content-address (`sha256` of the raw file bytes) so a later re-ingest can detect change;
- scan/OCR flags, size, and chunk counts produced in this phase.

## 2. Fields

| Field | Required | Notes |
|---|---|---|
| `id` | yes | `AR-ORG-001`. Persian digits in the file name or body are normalized first. |
| `language` | yes (nullable) | `fa` or `en`, taken from the `corpus/fa` or `corpus/en` folder. |
| `owning_node` | yes (nullable) | Primary `NodeIdentifier`, e.g. `N-HW-REP` for AR-HW-012. From the Phase 4 catalog (Phase 1 manifest). |
| `additional_nodes` | no | Other official owners, e.g. `N-CEO` for AR-ORG-001. |
| `doc_type` | yes | Knowledge class: `hr_policy`, `issue_file`, `team_guide`, … |
| `title_fa`, `title_en` | no | From the catalog / manifest. |
| `version` | yes | `1.0` for the current corpus. |
| `version_status` | no | `Approved` for the current corpus. |
| `date_jalali` | no | `1403-07` (Mehr 1403). Not converted unless a later phase asks. |
| `date_gregorian` | no | `2024-10`. |
| `confidentiality` | no | From the catalog; retrieval will honour it later. |
| `file_name`, `source_path` | file name yes | Path is local and may differ between machines. |
| `file_format` | yes | `docx`, `doc`, or `pdf`. |
| `file_sha256` | yes | SHA-256 of the un-normalized file bytes. |
| `byte_size` | yes | |
| `page_count` | no | Filled for PDF. Left null for DOCX (no reliable page number without rendering). |
| `char_count`, `chunk_count` | no | After normalization and chunking. |
| `is_scanned` | yes | True if any PDF page is image-only. LVM OCR is **not** run in this phase. |
| `bilingual_pair` | no | `{ "language": "en", "file_name": "AR-ORG-001-company-introduction.docx" }`. The pair shares `id`; they are not duplicates. |
| `ingested_at` | yes | UTC timestamp, ISO-8601. |

## 3. Validation

`rag_core.ingestion.application.metadata.validate_metadata` uses the `jsonschema` library. The corpus ingest script fails a file if its record does not validate.

## 4. What is not in the schema

Source anchors (`page`, paragraph, char offset, table cell) live on each **chunk**, not on the document record. See `source-reference-model.md`.
