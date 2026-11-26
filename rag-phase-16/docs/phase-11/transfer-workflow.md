# Phase 11 — Cyclic node processing and upward knowledge transfer

Kit version 0.11.0 (GitHub issue #11). Once per **processing cycle** every node of the ArmanRayan hierarchy summarizes what it knows for its parent. The summary is a **TransferPackage** whose detail level is decided by the layer that receives it. Packages are built bottom-up (teams first, the CEO last), checked against their own facts, judged with the Phase 10 rubric (18/20), stored in SQLite with history and exported as CSV.

There are no new dependencies. Unit tests never need Ollama, the GPU or the internet. The optional live step uses `qwen3:8b` (think off, JSON) on the local Ollama.

Target system: Ubuntu 24.04.5 LTS, Python 3.12.3, Ollama 0.40.2, project at `~/Desktop/RAG`.

## 1. Where things live

Issue #11 names `src/processing/` and `src/transfer/`. As in earlier phases the code sits inside the `rag_core` package: a new bounded context `rag_core.processing` and the existing Phase 3 context `rag_core.transfer`, extended rather than duplicated.

| Issue #11 output | Code |
|---|---|
| cyclic processing | `processing/domain/cycle.py` (`ProcessingCycle`, `StepResult`, `CycleReport`), `processing/domain/plan.py` (`TreeNode`, `build_plan`), `processing/application/services.py` (`CycleProcessor`), `processing/infrastructure/hierarchy_acl.py` |
| TransferPackage generation | `transfer/domain/items.py` (items, issue groups, capacity, `NodeKnowledge`), `transfer/domain/render.py` (facts and texts), `transfer/domain/builder.py` (`TransferPackageBuilder`), `transfer/application/services.py` (`TransferService`) |
| detail levels | `transfer/domain/levels.py` (`DetailLevelRule`, `DEFAULT_RULES`, `RuleBook`) |
| quality gate | `transfer/domain/review.py` (fact check + judge), `transfer/infrastructure/judging_acl.py` (package → Phase 10 judge case) |
| AI transfer suggestions | `transfer/domain/suggestions.py`, `SuggestionService` |
| CSV / DB storage of latest packages | `transfer/infrastructure/sqlite_store.py`, `transfer/infrastructure/csv_export.py` (uses the Phase 3 `csv_format.py`) |
| inputs from other contexts | `transfer/infrastructure/sources_acl.py` (hierarchy, lifecycle versions, issues, executors), `transfer/infrastructure/ike_acl.py` (Phase 9 leads and knowledge lacks) |
| settings | `config/transfer.yaml`, `transfer/infrastructure/config.py` |
| run + summary | `scripts/run_transfer_check.py` (called last by `scripts/setup_and_test.sh`) |
| tests | `tests/unit/processing/`, `tests/unit/transfer/test_transfer_*.py`, helpers `tests/fixtures/transfer/samples.py` |

Dependency direction stays hexagonal: the domain modules import only the shared kernel and their own context; everything that touches another context's aggregates is an anti-corruption layer (ACL) in `infrastructure/`; the cycle processor knows the transfer context only through a port (`NodeTransferPort`).

## 2. The cycle

* A cycle id is `YYYY-Qn` (quarter) or `YYYY-Mnn` (month), Jalali year; Persian digits are accepted. The kit runs **`1403-Q2`** (Tir–Shahrivar 1403). Its end, the end of Shahrivar 1403, is the reporting cutoff of AR-TRN-026 and the quarterly report of AR-FIN-008.
* `build_plan` turns the node registry into an ordered list of steps (sender → parent): deepest nodes first, ties by node id. It rejects duplicate nodes, more than one root, unknown parents and loops.
* Skipped: the root `N-BRD` (it only receives and hands resolutions down), the knowledge repository `N-LIB` (AR-TRN-026 §1: it supplies evidence and never summarizes upward), retired nodes and children of retired nodes.
* For the real registry: 21 nodes, **19 steps** — 15 teams/units → deputies (receiving layer L2), 3 deputies → CEO (L1), CEO → Board (L0).
* `CycleProcessor.run` keeps an inbox per node. A package goes into its parent's inbox **only if it was accepted**; a rejected package is stored (so the reason stays visible) but not forwarded. An exception in one node becomes a `failed` step; the cycle continues.

## 3. Detail levels

The receiving layer decides the level (`default_detail_level_received` in the layer registry, and every node's `transfer_detail_level_to_parent`; both are checked against the rules at every run).

| receiving layer | level | max units | max words (each language) | content |
|---|---|---|---|---|
| L0 Board | `executive` | 3 issues | 400 | top issues only; status, priority, progress, due date, decision amount, blocked count, item ids; **risks, decisions requested, source references** (required fields of L0, AR-TRN-026); no people, no documents; knowledge gaps as a count |
| L1 CEO | `managerial` | 6 issues | 800 | sub-issues grouped under their parent issue; per item lead, status, owner node, dependencies; list of knowledge gaps; capacity as counts |
| L2 deputy | `technical_summary` | 8 items | 1500 | one line per item (closed items included); lead, collaborators, dependencies, up to 3 documents, knowledge gaps per item; capacity per person |
| L3 team | `detailed_technical` | 12 items | 3000 | defined for completeness (L4 → L3 is not an upward package in this kit) |

Rules applied by `TransferPackageBuilder.build`:

1. own items + items of the accepted child packages are merged; one copy per item id, the owner's copy wins over a supporting node's copy;
2. closed / resolved items are dropped where the level does not show them (`dropped_closed` is recorded);
3. ranking: open first, open reserved (Board) decisions, blocked, priority, risk, status, id;
4. the best `max_items` units are kept; the rest are listed as **omitted**, never dropped silently; omissions of children travel up;
5. each language version must fit `max_words`; otherwise one unit less is rendered (never below one); a package that still does not fit is an error;
6. citations: owned active documents (item levels), the issue file and the item documents — only documents with an active version (Phase 5 lifecycle), written as `DOC@version`;
7. the Phase 3 `TransferPackage.assemble` enforces the L0 required fields and source citations.

## 4. Package content

`render.py` writes three things from the same input:

* **facts** — plain lines (package header, sender, counts, issue facts, group facts, item facts, knowledge gaps, capacity, documents, omitted). They are the only source of the texts.
* **English and Persian text** — deterministic templates. Every item line starts with the item id followed by its lead (so the Phase 10 rule judge can pair a lead with its sub-issue), no tables, no code fences.
* **fields** — `cycle, risks, decisions_requested, source_references, key_issues, summary, summary_fa, dependencies, knowledge_gaps, capacity, omitted, counts` (the CSV key/value rows).

Expected for 1403-Q2 (real data): deputies receive 13 items in total, the CEO 8 (two closed items dropped: AR-ISS-034 at N-HW, AR-ISS-036 at N-SW), the Board 6 items in 3 issues — AR-ISS-024 (four sub-issues, reserved decision on AR-ISS-024/LEG, decision amount 95 million toman), AR-ISS-032, AR-ISS-031 — with AR-ISS-035 and AR-ISS-033 listed as omitted.

## 5. Quality gate

`PackageReviewer.review`:

1. **fact check** of both language versions with the Phase 8 `CitedFactValidator` against the facts — every identifier and number must occur there;
2. **judge** — offline the Phase 10 rule judge (case kind `ike_summary`, expectation = included item ids, item leads, knowledge gaps); with Ollama, the live step additionally asks `qwen3:8b` (combined judge: both must accept);
3. accepted ⇔ grounded in both languages and every verdict accepted (18/20 and all criterion minimums).

Negative controls (offline, every run): each accepted package text is broken three ways — an invented amount (`777 million toman`), an invented issue id (`AR-ISS-099`), all item lines removed — and every copy must be rejected by the rule judge.

## 6. AI transfer suggestions (optional)

For the most important packages (Board brief, deputies, then teams with most items; `live.max_packages`, default 6), `qwen3:8b` gets the facts and returns JSON `{"summary", "raise", "reason"}`:

* `summary` — a short summary for the receiver (sentence limit per level);
* `raise` — item ids the receiver should act on first, chosen from the included and omitted items;
* `reason` — one sentence.

A suggestion is **accepted** only if the summary and reason are grounded, no raised id is invented, and the judges accept it. Raised ids that the deterministic package had omitted are reported as `additions` — the AI can propose moving them up, but the stored package itself stays the deterministic template. Suggestions are stored in their own table with revisions. Without Ollama the step is `skipped`; PASS never depends on it.

## 7. Storage

SQLite file `exports/transfer-packages/transfer-packages.sqlite`:

* `transfer_packages` — key (cycle, source node, revision), `is_latest`, target, layer, level, status, word counts, item count, SHA-256 `content_hash` of the canonical JSON content (no timestamps), payload;
* `transfer_suggestions` — the same idea per (cycle, node, language).

Saving the same content again is `unchanged` (no new row); changed content becomes revision n+1 and the old row stays as history with `is_latest = 0`. CSV export (`exports/transfer-packages/<cycle>/<NODE>.csv` + `latest-packages.csv`) is rewritten from the latest rows on every run and read back to compare fields, status, citations and target. Both folders are generated per run and ignored by git.

Re-run check (scratch database, every run): run the cycle twice — the second run must be 19 × `unchanged`; then simulate that N-HW-REP reports AR-ISS-024/HW as `resolved` — exactly the changed path gets revision 2 (N-HW-REP, N-HW, N-CEO), the other 16 stay unchanged, 22 rows in total.

## 8. Summary block and checks

`scripts/run_transfer_check.py` prints `======== PHASE 11 SUMMARY ========` … `======== END PHASE 11 SUMMARY ========` and writes `results/phase-11/transfer-check-<UTC>.json`.

Checks (all must be ok for PASS): `pytest`, `prior_steps` (ingest, dedup, hierarchy, issues, rag, ike, judge), `registry_loaded`, `records_built`, `plan_bottom_up`, `detail_levels_match_registry`, `packages_built`, `packages_grounded`, `packages_accepted`, `l0_required_fields`, `word_limits`, `negative_controls_rejected`, `store_idempotent`, `update_revision_history`, `csv_round_trip`.

## 9. Reference run

Test system: Ubuntu 24.04.5 LTS, Python 3.12.3; project at `~/Desktop/RAG`. Ollama 0.40.2, `qwen3:8b` (think off, JSON format).

- Run: 2026-11-19 14:40:11 UTC (2026-11-19 18:10 Tehran time, Asia/Tehran).
- Result: `status: PASS`, 1061 passed, 0 failed, 0 errors, 0 skipped; earlier steps ingest, dedup, hierarchy, issues, rag, ike and judge all exited 0.
- Cycle `1403-Q2`, period 1403-04-01..1403-06-31, trigger quarter close (AR-FIN-008 quarterly report).
- Plan: 19 senders, 2 skipped (`N-LIB` repository, `N-BRD` root), bottom-up; 15 packages to L2, 3 to L1, 1 to L0. Detail levels matched the registry (0 mismatches).
- Knowledge: 21 nodes, 26 active documents, 11 nodes with items, 14 items, 15 executors, 4 IKE leads, 5 IKE knowledge lacks.
- Packages: 19/19 built, 19 accepted, 0 rejected, 0 failed (technical_summary 15, managerial 3, executive 1). Items: 13 to L2, 8 to L1, 6 to L0; 2 issues omitted at L0 (named as omitted), 2 closed items dropped above L2.
- Board brief `N-CEO->N-BRD`: 6 items in 3 issues, 2 omitted, 142 / 136 words (fa / en). Largest managerial package `N-SW->N-CEO`: 5 items in 4 issues, 154 / 136 words. All packages far below the word limits.
- Fact check: grounded fa 19/19, en 19/19. Rule judge: 38/38 accepted, mean and minimum total 20/20.
- Negative controls: 104/104 rejected (wrong_number 38/38, fabricated_id 38/38, drop_items 28/28).
- Store: 19 inserted at revision 1. Re-run: 19 unchanged, 0 inserted, 0 updated (idempotent). Update `AR-ISS-024/HW@N-HW-REP -> resolved`: exactly 3 packages changed (N-HW-REP, N-HW, N-CEO), 16 unchanged, 22 rows, max revision 2, history ok.
- CSV: 20 files in `exports/transfer-packages/1403-Q2`, 0 round-trip problems.
- Live step: `ok`. Suggestions for 6 packages × 2 languages = 12; 0 parse errors; grounded 12/12; invented ids 0; additions 0; **accepted 0/12**.
- Live judging: suggestions rule 0/12, LLM 5/12, combined 0/12; template packages LLM 12/12, combined 12/12.

| package | lang | raised ids | rule | LLM |
|---|---|---|---|---|
| N-CEO | fa | AR-ISS-024/LEG, /HW, /WIN, /WEB, AR-ISS-032 | 16 | 0 |
| N-CEO | en | AR-ISS-024/LEG, /HW, AR-ISS-032 | 18 | 18 |
| N-SW | fa | AR-ISS-024/WIN, /WEB, AR-ISS-035, AR-ISS-031 | 8 | 7 |
| N-SW | en | AR-ISS-024/WIN, /WEB, AR-ISS-031, AR-ISS-035, AR-ISS-033 | 15 | 18 |
| N-ADM | fa | AR-ISS-024/LEG, AR-ISS-032 | 8 | 4 |
| N-ADM | en | AR-ISS-024/LEG, AR-ISS-032 | 15 | 18 |
| N-HW | fa | AR-ISS-024/HW | 8 | 9 |
| N-HW | en | AR-ISS-024/HW | 11 | 18 |
| N-ADM-FIN | fa | AR-ISS-024/LEG, AR-ISS-032 | 8 | 0 |
| N-ADM-FIN | en | AR-ISS-024/LEG, AR-ISS-032 | 15 | 15 |
| N-HW-REP | fa | AR-ISS-024/HW | 8 | 7 |
| N-HW-REP | en | AR-ISS-024/HW | 15 | 18 |

- Reading: the model invented nothing (grounded 12/12, no invented ids, every raised id was a real candidate already in the package). The rule judge scores a suggestion against the whole package checklist (all items with status, each lead next to its own item, the knowledge gaps); the suggestions were short, focused on a few issues and skipped the rest, so they scored 8–18 and none reached the bar on every criterion. Persian suggestions were weaker (five of six at 8). The LLM judge accepted 5/12 (all English, at 18) — the Phase 10 leniency of a self-judging model again — while the combined verdict rejected all of them.
- Design confirmed: the stored and forwarded package is the deterministic template (accepted by both judges 12/12 in the live step); AI suggestions are advisory, stored separately (12 rows) and never change a package.
- Live timings: suggestion average 4.238 s, judge average 2.62 s, tokens average 1403+196, total 113.8 s. All 15 checks ok.
- Results file: `results/phase-11/transfer-check-20261119T144011Z.json`.

## 10. Limits

* Package texts are templates: correct and checkable, not elegant prose. The AI suggestion is advice next to the package, not a replacement; in the reference run no suggestion passed (0/12) because they did not cover every item. A separate rubric for short advice, or a prompt that asks for all items, would be needed before suggestions can be accepted.
* Leads and knowledge gaps come from the Phase 9 IKE analysis of AR-ISS-024 only; the other issues show `lead none`.
* The rule judge checks ids, numbers, item coverage, lead pairing and language, not meaning; the live LLM judge is the same model family as the writer (see Phase 10 on self-judging bias).
* A rejected child package is not forwarded; the parent then reports `received packages k of n`, so the gap is visible upstream.

## 11. Deliver latest accepted package (UC-09)

`DeliverLatestPackage` lets the **parent** pull the newest accepted package of a
child for a cycle (`SqliteTransferStore.latest_accepted` /
`accepted_for_delivery`). Non-parents are rejected. If the newest revision is
rejected, the previous accepted revision is returned with warning
`latest_rejected_fallback`. Every delivery is written to
`transfer_deliveries` and to `deliveries.csv`.

**Score:** the response includes the rubric total out of 20 from the package's
stored review. When several verdicts exist, the **final accepted** verdict's
`total` is used (not a min or first-verdict rule).

<div dir="rtl">

## تحویل آخرین بستهٔ پذیرفته‌شده

والد می‌تواند آخرین بستهٔ پذیرفته‌شدهٔ فرزند را برای یک چرخه بگیرد. اگر
جدیدترین بازنگری رد شده باشد، بازنگری پذیرفتهٔ قبلی با هشدار
`latest_rejected_fallback` برمی‌گردد. امتیاز همان مجموع داوری ذخیره‌شده
(از ۲۰) است؛ اگر چند رأی باشد، مجموع آخرین رأی پذیرفته‌شده ملاک است. هر تحویل
در جدول `transfer_deliveries` و فایل `deliveries.csv` ثبت می‌شود.

</div>
