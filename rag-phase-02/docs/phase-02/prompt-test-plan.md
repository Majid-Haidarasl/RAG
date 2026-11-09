# Phase 2: Prompt Test Plan

Status: v1.1, updated after run `20261109-184242`; see §9 for the changes. Phase 2 output "prompt test plan" (spec 8.3, 19.2). It covers the Phase 2 baseline. Phase 14 extends it to all 12 prompt categories with larger sets.

## 1. Objectives

1. Measure whether the local candidates (bge-m3, qwen3:8b, qwen2.5vl:3b) are usable for the core RAG tasks in FA and EN.
2. Set a reproducible baseline (same data, prompts, seeds and parameters) that later prompt or model changes are compared against.
3. Decide on qwen3 thinking mode per task type, based on measured quality gain and latency cost.
4. Check that structured outputs (decomposition, judge) are parseable without manual repair (MP-08).

## 2. Prompt registry

Templates are in `config/prompt-registry.json`. Each has an `id`, a semver `version`, a `task_type`, a spec 8.3 category, linked metrics, an output format and, for JSON tasks, a schema. Any wording change bumps the version and needs a re-run. Every logged run (`llm_runs.jsonl`) stores `prompt_id` and `prompt_version`.

| Prompt | Spec 8.3 category | Output | Metrics |
|---|---|---|---|
| `qa.grounded` v1.0.0 | Q&A | text with `[chunk_id]` citations, or `INSUFFICIENT_CONTEXT` | MP-02, C-16, C-43 |
| `summary.transfer` v1.0.0 | Transfer preparation; managerial and technical summaries | executive (≤ 80 words) or technical (120–250 words) | MP-03, C-24 |
| `issue.decompose` v1.1.0 | Issue decomposition (**schema `format` by default** since round 2) | JSON (decompose_schema) | MP-04, MP-08, C-29 |
| `judge.score` v1.0.0 | LLM-as-judge (answers) | JSON: faithfulness, completeness, citation, clarity, 4 × 0–5 = /20, accept if ≥ 18 | C-41, MP-08 |
| `judge.summary` v1.0.0 | LLM-as-judge (transfer summaries) | JSON: faithfulness, coverage, level_fit, clarity; no citation criterion | MP-03, C-41 |
| `lvm.read` v1.0.0 | Visual interpretation | text or JSON | C-08 |

Design rules under test:
- Instructions go in the system message. Context and question go in the user message.
- Context blocks are labelled with their chunk IDs.
- The answer language is set explicitly.
- Refusal uses a fixed machine-checkable token, `INSUFFICIENT_CONTEXT`.
- Numbers and IDs must be copied unchanged.

## 3. Test data

All data comes from the ArmanRayan corpus v1.0. See `experiments/phase-02/data/README.md`.

- 24 chunks: 12 topics × FA/EN.
- 30 gold questions (20 FA, 10 EN). 12 FA questions also have language-neutral facts for the cross-lingual test.
- 4 unanswerable questions for refusal.
- Decomposition input: AR-ISS-024. Expected domains are HW, WIN and LEG. Expected executors are Akbari/Javadi, Mohseni and Jalali.
- 4 judge cases: a good and a wrong answer in each language. The wrong answers contain incorrect numbers and no citation.
- 3 images: org chart, FIN-008 table, scanned FA SLA page.

## 4. Test matrix

| Task | FA | EN | Cross-lingual | Think off | Think on | Variants / repeats | Full run calls | Quick run calls |
|---|---|---|---|---|---|---|---|---|
| Retrieval (bge-m3) | 20 | 10 | FA→EN, EN→FA | n/a | n/a | 5 index modes | 3 batch + 10 single | same |
| Grounded QA | 20 | 10 | 12 (FA question, EN context) | ✓ | 6 cases | — | 48 | 7 + 1 think-on |
| Refusal | 2 | 2 | — | ✓ | 1 case | — | 5 | 2 |
| Transfer summary | exec + tech | exec + tech | — | ✓ | fa-executive | judged by `judge.score` | 5 + 4 judge | 2 |
| Decomposition | ✓ | ✓ | — | ✓ | 1 per language | prompt-only vs schema `format`; 3 repeats (r1–r2 at temperature 0.7) | 14 | 2 |
| Judge | 2 | 2 | — | ✓ | 2 bad cases | 2 repeats | 10 | 2 |
| LVM | 1 FA question + OCR | 5 | — | n/a | n/a | — | 7 | 2 |

## 5. Scoring rules (automatic)

- **Fact match.** Both the text and the expected facts are normalized first: Persian/Arabic digits become ASCII; `٬`, `,` and the Arabic comma `،` (U+060C) are dropped when used as thousands separators; `٫` becomes `.`; ZWNJ becomes a space; Arabic ي/ك become ی/ک; text is lowercased. A fact group counts as hit if any of its alternatives is a substring. `fact_rate` = groups hit / groups. `all_facts` = every group hit.
- **Citation.** `citation_ok` = at least one cited `[chunk_id]` is a relevant chunk. `citation_precision` = relevant citations / all citations.
- **Refusal.** The answer contains `INSUFFICIENT_CONTEXT` or a listed refusal phrase. `false_refusal` = refusal on an answerable question.
- **JSON.**
  - `json_valid`: output parses, after stripping `<think>` and code fences.
  - `schema_valid`: passes the registry schema (types, required fields, enum, item count 2–6).
  - `domain_recall`: share of HW/WIN/LEG present.
  - `executor_match_rate`: share of expected domains whose suggested executor matches.
  - `executor_coverage`: label-independent; is each expected owner assigned somewhere?
  - `executor_name_exact_rate`: owner names copied exactly from the EXECUTORS list. Catches Persian name corruption.
- **Judge.**
  - `sum_consistent`: the criterion scores sum to `total`.
  - `verdict_correct`: computed total ≥ 18 agrees with the expected verdict.
  - Discrimination: good answers should score ≥ 18 and bad answers < 18.
- **Retrieval.** Recall@1/3/5 is a hit of any relevant chunk in the top k. MRR is the mean of 1/rank. FA↔EN parallel-chunk cosine gap shows cross-lingual alignment.
- **Performance.**
  - Tokens/s = `eval_count / eval_duration`.
  - TTFT = time from request to the first streamed token, thinking included.
  - "First answer token" = time to the first content token.
  - Wall-clock p50 and p95.
  - Truncation rate.
  - VRAM from `/api/ps` (`size_vram`) and the `nvidia-smi` peak per stage.

## 6. Pass criteria (from Phase 1 evaluation-baseline.md)

| Metric | Phase 1 target | Phase 2 reading |
|---|---|---|
| MP-01 / C-14 | Recall@5 ≥ 0.80 and MRR ≥ 0.60 | Indicative only: 24 chunks is a very small index. The real check is in Phase 8 on the full chunked corpus. |
| MP-02 / C-16 | Faithfulness ≥ 4/5 on ≥ 90%; citation correctness ≥ 0.90 | `citation_ok_rate` ≥ 0.90; FA and EN `fact_rate` reported separately |
| C-16 abstention | refuse when knowledge is missing | `correct_refusal_rate` = 1.0 on the 4 cases, `false_refusal_rate` ≤ 0.05 |
| MP-03 | judge ≥ 18/20 on transfer summaries | `judge_on_summaries`. Self-judging with the same model is a known bias; human review required. |
| MP-04 | ≥ 80% decompositions accepted by human review | Automatic `domain_recall` and `executor_match` plus human review of `llm_runs.jsonl` |
| MP-08 | 100% schema-valid across repeated runs | `schema_valid_rate` for prompt-only and for schema `format` |
| C-41 | judge–human agreement ±2 | Phase 2 only checks verdict accuracy on 4 planted cases. The agreement study is Phase 10. |

## 7. Procedure

1. Run `bash setup.sh`. It runs the unit tests and the environment check.
2. Run `run_all.py --quick` to catch setup problems. Then run the full `run_all.py` with the GPU otherwise idle.
3. Send back the copy-paste block and `phase02-results-<run>.zip`.
4. Human review:
   - Read `llm_runs.jsonl` for decompositions (MP-04), summaries (MP-03) and every failed QA case.
   - Mark each one accept or reject and give a reason.
5. Fill in `offline-model-baseline.md` and set registry statuses.

## 8. Known limitations

- The sets are small (30 questions, 4 judge cases, 3 images). Results are a baseline, not statistically strong.
- Substring fact matching can miss correct paraphrases, such as a number written in words. Failed cases are reviewed by hand.
- The same model generates and judges. Judge results are therefore indicative only.
- Timings depend on what else is using the GPU.

## 9. Changes after the first real run (20261109-184242)

Every failing case was inspected by hand. The full table is in `offline-model-baseline.md` §7. The following kit and plan changes resulted.

| Change | Reason | Effect |
|---|---|---|
| Normalization treats `،` (U+060C) as a thousands separator | qwen3 wrote "۸،۴۷۰"; correct answers scored 0 (FA-09-cross think-on, FA-10-cross) | Cross-lingual fact rate 0.79 → 0.917 (rescored) |
| Gold data v1.1 | FA-20 now accepts "الف"; EN-08 reworded (the RFP ID was not in the chunk); RAM also accepts "حافظه"/"memory"; org-reporting also accepts "Chief Executive Officer"/"مدیرعامل" | Removes false failures. Real errors are untouched (FA-15 "دجANGO", FA-18 refusal, scan "20 minutes"). |
| New `judge.summary` rubric | Summaries were judged with the QA rubric, so "citation = 0" made SUM-fa-executive 15/20 | MP-03 must be re-measured |
| `issue.decompose` 1.1.0 with domain definitions and an exact-name rule | LEG work labelled FIN/OTHER; FA runs never created WIN; Persian names corrupted | Re-run needed |
| New metrics `executor_coverage` and `executor_name_exact_rate` | The strict label metric hid that the owners were often right | FA coverage 0.667, EN 1.00; name exactness 0.93–0.97 |
| `tools/rescore.py` | Re-scores saved outputs without model calls | Used for the "rescored" columns |

Additional rules added to the plan:
- Every automatic failure is inspected and classified as **model** or **kit** before it is reported.
- The judge is not used alone for MP-03 until the Phase 10 agreement set exists.
- The re-run with kit 0.2.0 (`--only llm` and `--only vram`) was the Phase 2 close-out check. It was done in round 2 (§10).

## 10. Round 2 results (kit 0.2.0, run 20261109-191910) and resulting changes

| Item | Round 2 result | Change |
|---|---|---|
| `issue.decompose` 1.1.0 + schema `format` | JSON and schema valid 1.00; domain recall 0.94; exact names 1.00; 5.67 sub-issues | **Schema mode becomes the default** for decomposition and structured JSON. Over-splitting is not scored yet; human check in Phase 9/10. |
| `issue.decompose` 1.1.0, prompt-only | Schema valid 0.83, domain recall 0.83, 4.33 sub-issues; **1 malformed JSON** (`fa-prompt_only-r1`) | Prompt-only is a fallback only |
| JSON parser (kit bug) | Kit 0.2.0 recovered an inner object from the malformed reply and logged `json_valid = true` | **Kit 0.2.1:** the parser takes only the outermost object and reports `malformed-json` / `unterminated-json`. Unit test added; `rescored.json` gives prompt-only JSON-valid 0.83. |
| `judge.summary` 1.0.0 | 20/20 on all 4 summaries | Passes ≥ 18 per the judge only. It scored 20/20 a FA summary with an unsupported "۲ ماه" claim. MP-03 still needs a human check and a code-level number/duration check. |
| Data v1.1 | EN QA 1.00 / 1.00; cross 0.92 | Confirms the round-1 rescore |
| Think-on budget | 1 of 12 think-on calls truncated in thinking (en decompose, 2048 tokens, 37.4 s, empty answer) | `THINK_NUM_PREDICT` raised to 4096 (kit 0.2.1); fallback is think off + schema |
| Offline (C-17) | Run 20261109-190709: network off, 86/86 ok, same scores | C-17 passed for the LLM stage |

Model errors that repeated deterministically (same seed): FA-18 false refusal with think off, FA-19 wrong citation, FA-15-cross "دجANGO". They go to the Phase 14 prompt backlog and the Phase 3 validator.
