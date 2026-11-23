# Phase 14 — Updated metrics

Measured numbers of the Phase 14 reference run, taken from its PHASE 14 SUMMARY block.

Run: 3 Azar 1405, about 00:30 Tehran time, on Fedora Linux, Python 3.15.2, Ollama 0.40.17, `qwen3:8b` + `bge-m3` (think off).
Results file: `eval/results/phase-14-check-20261123T210037Z.json` (tables: `eval/results/updated-metrics-20261123T210037Z.md`).
Result: **PASS**, all 12 checks `ok`, live step `ok`.

## 1. Kit

| Item | Expected | Measured |
|---|---|---|
| pytest | 1355 + 138 = 1493 passed | **1493 passed**, 0 failed, 0 errors, 0 skipped |
| earlier steps | all 0 | ingest, dedup, hierarchy, issues, rag, ike, judge, transfer, projects, rfp = 0 |
| offline checks | 12 ok, `status: PASS` | 12/12 ok, PASS |
| gold set | 32 items, 16 pairs, 28 answered, 4 refusals, Phase 8 10/10, 0 problems / 0 grounding / 0 scope | as expected |
| calibration | 14 + 28 = 42; drop_fact 3, wrong_number 2, wrong_language 4, fake_label 3, refuse_answerable 2 | as expected |
| rule judge on the 42 cases | derived 14/14 + 14/14, only `CAL-N06` wrong (41/42) | 41/42, kappa 0.952, leniency 0.050; every mutation kind rejected |
| prompt renders | 0 problems | 88 rendered, 0 problems |
| id controls (fake model) | baseline 0/2, listed 0/2, listed_retry 2/2 | as expected |

## 2. Retrieval (28 answered items)

| Variant | hit@1 | hit@3 | hit@5 | MRR | context facts | Q06 rank fa / en | Q06 context facts |
|---|---|---|---|---|---|---|---|
| baseline (offline BM25) | 0.857 | 0.893 | 0.929 | 0.884 | 62/62 | 2 / 4 | 4/4, 4/4 |
| wide (offline) | 0.857 | 0.893 | 0.929 | 0.884 | 62/62 | 2 / 4 | 4/4, 4/4 |
| lexical_boost (offline) | 0.857 | 0.893 | 0.929 | 0.884 | 62/62 | 2 / 4 | 4/4, 4/4 |
| wide_lexical (offline) | 0.857 | 0.893 | 0.929 | 0.884 | 62/62 | 2 / 4 | 4/4, 4/4 |
| baseline (live hybrid) | 0.750 | – | 0.929 | 0.833 | 62/62 | 1 / 3 | 4/4, 4/4 |
| wide (live) | 0.750 | – | 0.929 | 0.833 | 62/62 | 1 / 3 | 4/4, 4/4 |
| lexical_boost (live) | 0.786 | – | 0.893 | 0.839 | 62/62 | 1 / not in top 5 | 4/4, 4/4 |
| wide_lexical (live) | 0.786 | – | 0.929 | 0.846 | 62/62 | 1 / 5 | 4/4, 4/4 |

All 28 items were fully covered (`full=28/28`) with 0 scope violations in every variant. The live summary does not print hit@3.

Reference point: Phase 8 on its 8 answered sample questions had hit@5 0.875 and MRR 0.775 (offline).

## 3. Q&A prompts (32 items, live, retrieval variant `wide` from `config/eval.yaml`)

| Prompt | status ok | facts | grounded | citations valid | rule accept | detail ok | gen avg / p95 s | Q06 facts (fa / en) |
|---|---|---|---|---|---|---|---|---|
| qa.answer@2.0.0 | **32/32** | **62/62** | 32/32 | 33/33 | **28/28** | 32/32 | 2.67 / 4.59 | 4/4 / 4/4 |
| qa.answer_complete@3.0.0 | 31/32 | 60/62 | 32/32 | 33/33 | 26/28 | 31/32 | 2.76 / 4.67 | 4/4 / 4/4 |

Reference point: Phase 8 Q06 found 2 of 3 facts; P06 now has 4 fact groups (including web reporting) and both prompts found all 4.

## 4. Judge prompts (42 calibration cases, live)

| Prompt | agreement | kappa | leniency | false accepts | false rejects | errors | avg s | rejected per mutation |
|---|---|---|---|---|---|---|---|---|
| baseline (judge.qa@1.0.0) | 35/42 | 0.661 | 0.350 | 7 | 0 | 0 | 1.27 | drop_fact 1/3, fake_label 3/3, refuse_answerable 0/2, wrong_language 3/4, wrong_number 2/2 |
| strict (judge.qa.strict@2.0.0) | **36/42** | **0.712** | **0.200** | **4** | 2 | 0 | 1.06 | drop_fact 1/3, fake_label 3/3, refuse_answerable **2/2**, wrong_language 3/4, wrong_number 2/2 |
| rule judge (offline) | 41/42 | 0.952 | 0.050 | 1 (`CAL-N06`) | 0 | – | – | all 14/14 |

Leniency is the share of the 20 gold rejects (6 Phase 10 + 14 derived) that a judge accepted. Reference point: Phase 10 live calibration with the baseline prompt agreed 12/14 (accepted `CAL-N03` and `CAL-N06`).

## 5. Required ids (four Phase 13 AI texts, live)

| Variant | ids named | all ids | accepted | invented ids | retries | avg s |
|---|---|---|---|---|---|---|
| baseline | 11/18 | 1/4 | 2/4 | 0 | 0 | 5.20 |
| listed | 9/18 | 1/4 | 1/4 | 1 | 0 | 6.04 |
| listed_retry | **15/18** | **3/4** | 2/4 | 1 | 3 | 9.65 |

Reference point: in Phase 13 the four AI texts named 3/4, 2/2, 2/4 and 1/2 required ids; 2 of 4 were accepted.

## 6. Choices

| Kind | Configured | Measured winner | Agrees | Script's reason |
|---|---|---|---|---|
| retrieval | wide | **baseline** | **NO** | context facts tie (62/62 everywhere); no gain above 0.02, keep baseline |
| qa_prompt | qa.answer_complete | **qa.answer** | **NO** | facts 62/62 vs 60/62 |
| judge_prompt | strict | strict | yes | accuracy 0.857 vs 0.833 |
| ai_ids | listed_retry | listed_retry | yes | accept rate tie (0.5 vs 0.5); wins on mention rate |
| generation_model | qwen3:8b | not compared (one installed model) | – | – |
| embedding_model | bge-m3:latest | not compared | – | – |

`config/eval.yaml` is committed exactly as it was tested. The two defaults that disagreed (`retrieval` → `baseline`, `qa_prompt` → `qa.answer`) are switched in Phase 15 and re-verified on the target system.

## 7. Live timings

| Step | Seconds |
|---|---|
| retrieval (4 variants, cached embeddings) | 5.4 |
| Q&A (2 prompts × 32) | 179.1 |
| judges (2 prompts × 42) | 97.9 |
| required ids (3 variants × 4 texts, 3 retries) | 83.6 |
| **total live** | **≈ 366 (about 6 minutes)** |

## 8. Reading

- **Q06 is solved:** 4 of 4 causes in both languages with both prompts; every retrieval variant brings all four into the context.
- **Retrieval:** the variants are practically equal on this gold set because the context already holds all 62 fact groups; `wide_lexical` has a slightly better live MRR (0.846 vs 0.833) but that is not above the minimum gain. The configured `wide` was not justified by the measurement.
- **Q&A prompt:** the Phase 8 prompt did better (62/62 facts, 28/28 accepted) than the new list prompt (60/62, 26/28). The configured `qa.answer_complete` was not justified by the measurement.
- **Judge:** the checklist prompt cut false accepts from 7 to 4 (kappa 0.661 → 0.712) and fixed refusals of answerable questions, but **dropped facts are still missed** (1/3 with either prompt). The rule judge remains the deciding check.
- **Required ids:** the retry raised named ids from 11/18 to 15/18, but one id was invented and acceptance stayed at 2/4; AI texts remain advisory.
