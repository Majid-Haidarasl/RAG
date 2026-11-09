# Phase 2: Offline Model Baseline Report

Status: **v1.1.** Filled from real run `20261109-184242` and three confirmation runs on the same PC (Ubuntu 24.04.5): `20261109-190709` (offline), `20261109-191910` (kit 0.2.0, LLM) and `20261109-192721` (kit 0.2.0, VRAM). See section 11.
Raw files are in `experiments/phase-02/results/20261109-184242/`. Every number below is copied from `results.json`, or from `rescored.json` where marked **(rescored)**. Nothing is estimated unless it is labelled *projection*.

**How to read "as-run" vs "rescored".** The run used kit 0.1.0. When I inspected every failing case, some failures turned out to be scoring or gold-data defects in the kit, not model errors (section 7). `tools/rescore.py` applies the fixed scoring (kit 0.2.0, data v1.1) to the **same saved model outputs** without calling any model. Both columns are reported. Decisions use the rescored column only where the failure was demonstrably a kit defect.

## 1. Run identification

| Field | Value |
|---|---|
| Run ID | `20261109-184242`, FULL mode, 7.16 min (embed 0.48, LLM 5.93, LVM 0.58 min) |
| Date | 2026-11-09, 18:42 (Asia/Tehran) |
| Kit / prompt registry | kit 0.1.0, registry 0.1.0 (all prompts v1.0.0) |
| Ollama | 0.40.2; `think` API field supported (think_mode = `api` on every call) |
| OS / Python | Ubuntu 24.04.5 LTS / Python 3.12.3 |
| Hardware | i5-12400F · 16 GB RAM · RTX 3060 12 GB · driver 595.99.02 (CUDA 13.2). Desktop uses 490 MiB of VRAM before the run. |
| Calls | LLM 86/86 ok, LVM 7/7 ok, 0 errors, 0 truncations |
| Network during run | Not recorded for this run. The offline check is run `20261109-190709` (section 11). |
| Confirmation runs | `20261109-190709` offline LLM; `20261109-191910` kit 0.2.0 `--only llm`; `20261109-192721` kit 0.2.0 `--only vram` (section 11) |

## 2. Candidate models (from `check_env`)

| Role | Model | Disk | Params / quant | Max context | Context used |
|---|---|---|---|---|---|
| Embedding | bge-m3:latest | 1.16 GB | 566.70M, F16 | 8192 | Ollama default 4096 in this run (see §6) |
| LLM | qwen3:8b | 5.23 GB | 8.2B, Q4_K_M | 40960 | 8192 |
| LVM | qwen2.5vl:3b | 3.2 GB | 3.8B, Q4_K_M | 128000 | 8192 |

## 3. Embedding baseline (bge-m3)

- Embedding dimension: 1024.
- Cold first call (includes model load): 11.20 s.
- Single-text latency: mean 13.1 ms, p50 10.9 ms, p95 19.8 ms.
- Batch call: 283.6 ms per chunk and 359.3 ms per question. That is slower than single calls. It was measured once and is unexplained. Kit 0.2.0 measures a second, warm batch.

| Mode | n | R@1 | R@3 | R@5 | MRR | MP-01 / C-14 (R@5 ≥ 0.80, MRR ≥ 0.60) |
|---|---|---|---|---|---|---|
| FA → FA | 20 | 0.85 | 0.95 | 0.95 | 0.906 | pass |
| EN → EN | 10 | 0.90 | 0.90 | 1.00 | 0.925 | pass |
| FA → EN (cross-lingual) | 20 | 0.90 | 0.95 | 0.95 | 0.932 | pass |
| EN → FA (cross-lingual) | 10 | 0.90 | 1.00 | 1.00 | 0.950 | pass |
| Mixed bilingual index | 30 | 0.867 | 0.933 | 0.967 | 0.911 | pass |

FA↔EN cross-lingual alignment: parallel chunks have mean cosine 0.827, non-parallel pairs 0.462, a gap of 0.366. bge-m3 aligns Persian and English well.

**Top-1 failures and causes.** These are real retrieval errors; the gold data is correct.
- **FA-09 and FA-15 → `ORG-001`.** The company name "آرمان‌رایان" in the question pulls the query toward the company-profile chunk. The correct chunk still ranks 2nd.
- **FA-19 and EN-07 → `HW-014` / `LEG-009`.** These are "who is the executor" questions. They match chunks full of person and role names. The `ISS-024` chunk mixes a narrative paragraph with a table, which dilutes its vector.

**Reading.** With only 24 chunks these numbers are indicative, not a pass of MP-01 for the system. They do show that bge-m3 is not the bottleneck for FA, EN or cross-lingual retrieval.

## 4. LLM baseline (qwen3:8b)

### 4.1 Performance

| Think | n | tokens/s | TTFT p50 | First answer token p50 | Wall p50 | Wall p95 | Output tokens mean | Thinking chars mean | Truncated |
|---|---|---|---|---|---|---|---|---|---|
| off | 74 | 57.8 | 0.34 s | 0.34 s | 1.36 s | 13.50 s | 161 | 0 | 0 |
| on | 12 | 56.7 | 0.17 s | 5.94 s | 7.53 s | 20.97 s | 506 | 1405 | 0 |

- QA answers take about 1–2 s with think off. Decomposition takes 9–15 s with think off and 17–26 s with think on.
- The kit's `prompt_tokens_per_s` (8,888 and 24,316 mean) is not a usable number because Ollama reuses the KV cache for identical system prompts.

### 4.2 Quality (think off)

| Task | Metric | As-run | Rescored | Phase 1 target | Verdict |
|---|---|---|---|---|---|
| QA FA (20) | fact_rate / all-facts | 0.93 / 0.90 | **0.95 / 0.95** | — | good |
| QA FA | citation_ok | 0.90 | 0.90 | ≥ 0.90 (C-16) | at the threshold |
| QA FA | false refusal | 0.05 (1/20) | 0.05 | ≤ 0.05 | at the threshold |
| QA EN (10) | fact_rate / citation_ok | 0.90 / 0.90 | 0.90 / 0.90 | ≥ 0.90 | at the threshold; the only miss is a gold defect (EN-08) |
| QA cross (FA question, EN context, 12) | fact_rate | 0.79 | **0.917** | — | good; 1 real error |
| QA cross | citation_ok | 1.00 | 1.00 | ≥ 0.90 | pass |
| Refusal (4 unanswerable) | correct refusal / exact token | 1.00 / 1.00 | 1.00 | 1.00 (C-16) | pass |
| Summary executive (2) | fact_rate / within limit | 0.83 / 1.00 | **1.00** / 1.00 | — | pass |
| Summary technical (2) | fact_rate / within limit | 1.00 / 1.00 | 1.00 | — | pass |
| Summary judge | total /20 (fa-exec, fa-tech, en-exec, en-tech) | 15, 20, 20, 20 | not rescorable; needs a re-run with `judge.summary` | ≥ 18 (MP-03) | **not measurable yet**: rubric bug plus a lenient judge (§7) |
| Decomposition, prompt only (6) | JSON / schema valid | 1.00 / 1.00 | 1.00 / 1.00 | 100% (MP-08) | pass |
| Decomposition, schema `format` (6) | JSON / schema valid | 1.00 / 1.00 | 1.00 / 1.00 | 100% (MP-08) | pass; no gain over prompt-only |
| Decomposition | strict domain recall (prompt / schema) | 0.72 / 0.67 | 0.72 / 0.67 | — | weak |
| Decomposition | executor coverage, any label (prompt / schema) | — | **0.83 / 0.83** (FA 0.667, EN 1.00) | ≥ 80% human acceptance (MP-04) | FA below; needs human review |
| Decomposition | executor names copied exactly (prompt / schema) | — | 0.97 / 0.93 | 100% | **fail on Persian** |
| Judge (8 = 4 cases × 2) | JSON valid / sum consistent / verdict accuracy | 1.00 / 1.00 / 1.00 | same | 100% | pass. Good answers 20/20; bad answers 3–7/20. |

### 4.3 Thinking mode: on vs off (6 QA, 1 refusal, 1 summary, 2 decomposition, 2 judge)

| Case | Metric | Off | On (as-run → rescored) | Wall off → on |
|---|---|---|---|---|
| QA FA-18 | fact_rate | 0.00 (false refusal) | 1.00 | 1.3 → 8.4 s |
| QA FA-09-cross | fact_rate | 1.00 | 0.00 → **1.00** (Arabic-comma scoring bug) | 1.4 → 5.8 s |
| QA FA-20 | fact_rate | 0.50 → 1.00 | 0.50 → 1.00 | 1.2 → 7.0 s |
| QA FA-09, EN-03, EN-07 | fact_rate | 1.00 | 1.00 | 1.0–1.5 → 3.3–5.9 s |
| Refusal REF-FA-02 | refused | yes | yes | 0.9 → 4.9 s |
| Summary fa-executive | fact_rate | 1.00 | 1.00. Removes the invented "۲ ماه" but adds legal/finance lines. | 4.3 → 9.9 s |
| Decompose fa | schema valid / domains | valid; no WIN | valid; WIN present but assigned to Farzaneh Javadi (wrong owner) | 13.1 → 26.0 s |
| Decompose en | schema valid | valid | valid; LEG labelled OTHER | 9.9 → 16.9 s |
| Judge FA-BAD, EN-BAD | verdict correct | yes | yes | 1.6–2.4 → 8.0–8.9 s |

Thinking fixed one real error out of 12 paired cases (FA-18, an over-cautious refusal). It never made quality worse once scoring was corrected. It costs 3–7× the latency and about 3× the output tokens.

## 5. LVM baseline (qwen2.5vl:3b)

- First call (model load): 11.5 s.
- Wall p50: 2.5 s.
- Decode speed: 107 tok/s.
- Input size: about 1,360 prompt tokens per image.

| Image | Task | As-run | Rescored | Missing / error |
|---|---|---|---|---|
| org_chart.png | org-extract | 1.00 | 1.00 | — |
| org_chart.png | org-reporting | 0.50 | **1.00** | Answered "the Chief Executive Officer" (role, not name). Gold was too strict. |
| org_chart.png | org-fa-question (FA) | 1.00 | 1.00 | — |
| revenue_table.png | table-extract (JSON) | 1.00 | 1.00 | All 9 numbers exact; valid JSON. |
| revenue_table.png | table-qa | 1.00 | 1.00 | — |
| scanned_sla_fa.png | scan-ocr (FA) | 0.92 | 0.92 | Read **۳۰ as 20**. Wrote "آرمان‌ریان" and "022-AR-SW" (bidi-reversed ID). |
| scanned_sla_fa.png | scan-qa | 0.50 | 0.50 | Said "20 minutes"; the correct value is 30. A real model error. |
| **Mean** | | 0.845 | **0.917** | |

**Reading.** Clean rendered charts and tables are reliable, including Persian labels. On a degraded Persian scan the model misreads digits (۳ → ۲). That is a correctness risk for numbers.

## 6. VRAM and resources

| Snapshot (as recorded) | `/api/ps` | nvidia-smi used | Valid? |
|---|---|---|---|
| Before | none | 490 MiB | yes |
| After embedding | bge-m3 633 MB (ctx 4096) | 1,322 MiB | yes |
| After LLM | qwen3:8b 6,004 MB, all on GPU (ctx 8192) | 6,711 MiB (peak 6,711) | yes |
| After LVM | qwen2.5vl:3b 2,997 MB **listed twice** | 9,396 MiB | **no**: duplicate runner |
| "Co-resident embed+llm" | qwen3 5,015/6,270 MB on GPU (**partly on CPU**) + bge-m3 633 + qwen2.5vl 2,997 | 10,891 MiB (stage peak 9,777) | **no**: three models loaded |

**Kit bug.** Ollama unloads asynchronously, and here it had two LVM runners. Kit 0.1.0 sent one `keep_alive: 0` request and never checked that the model was gone. As a result the LVM stayed loaded during the co-residency check, and qwen3 was pushed partly onto the CPU. Kit 0.2.0 fixes this:
- `unload()` repeats the request and verifies the result via `/api/ps`.
- `unload_all()` clears the GPU before every stage.
- Snapshots flag duplicate runners and CPU offload.
- A new `vram` stage starts from an empty GPU.

I reproduced the bug and the fix with `mock_ollama.py --dup-lvm`.

**Measured co-residency (run `20261109-192721`, kit 0.2.0 `--only vram`, starting from an empty GPU):**

| Snapshot | `/api/ps` | nvidia-smi used | Offload |
|---|---|---|---|
| Empty GPU | none | 587 MiB | — |
| Embedding + LLM | qwen3:8b 6,004 MB + bge-m3 633 MB | **7,496 MiB** | none, all on GPU |
| Embedding + LLM + LVM | + qwen2.5vl:3b 2,429 MB | 11,347 MiB (peak 11,351) | **qwen2.5vl:3b partly on CPU** |

Embedding + LLM use 7.3 GiB, which leaves about 4.7 GiB free on the 12 GiB card. All three models do not fit: the LVM spills to the CPU. This replaces the earlier ~7.5 GiB projection, which turned out close.

## 7. Failure analysis: model error or kit defect?

| Case | Symptom | Cause | Class |
|---|---|---|---|
| FA-18 mono, think off | INSUFFICIENT_CONTEXT although `fa-ISS-024-c1` was in context | The chunk says "نشانه اصلی" (symptom) and "تأخیر … سهم دارد", while the question asks for "علت". The model was too literal. Think-on answered correctly. | **Model**: over-cautious grounding |
| FA-19 mono | Correct name (مهسا جلالی) but cited `fa-LEG-009-c1` | Cited the chunk about her role instead of the ISS-024 table | **Model**: citation error |
| FA-20 mono, both think modes | Answered "پیشنهاد الف … ۷۸٫۸" without the company name شفق | The answer is correct. Gold required the company name. | **Kit**: gold too strict (now accepts الف) |
| EN-08 mono | Refused | The question cites RFP ID AR-RFP-1403-07, which is **not in the chunk**. Refusing is defensible. | **Kit**: gold defect (question reworded in data v1.1) |
| FA-09-cross (think on), FA-10-cross | "۸،۴۷۰" and "۱،۱۷۰" scored 0 | The model used the Arabic comma U+060C as thousands separator; normalization ignored it. | **Kit**: scoring bug (fixed) |
| FA-15-cross | "دجANGO" | Persian answer from English context corrupted the token "Django" | **Model**: mixed-script token corruption |
| FA-18-cross | "…چند سation…" and "حافظه" instead of RAM | Memory = RAM is semantically fine and now accepted. The "سation" corruption is real. | Mixed: kit (synonym) + model (corruption) |
| summary en-executive | RAM "missed" | Wrote "server memory" | **Kit**: gold too strict |
| SUM-fa-executive = 15/20 | citation = 0 | Summaries were judged with the **QA rubric**, which includes a citation criterion, although the summary prompt asks for no citations. The same judge gave en-executive citation = 5 with no citations, so it was also inconsistent. It gave faithfulness = 5 even though fa-executive contains an unsupported "تأخیر ۲ ماه" and a garbled phrase ("تحویل سهمیه گزارش وب"). | **Kit** (wrong rubric) + **model** (lenient, inconsistent judge) |
| Decomposition domain recall 0.67–0.72 | LEG labelled FIN or OTHER; FA runs never create WIN | Penalty/amendment items labelled FIN is a taxonomy ambiguity (no domain definitions in prompt v1.0.0). The owner was still always Mahsa Jalali in FA. Missing WIN in all 6 FA think-off runs is a real Persian decomposition weakness. | Kit (taxonomy) + **model** (FA misses the Windows stream) |
| Decomposition FA names | "فرزانه جوتادی", "فرزانه جو با" (3 of 6 FA runs) | Persian name copying corrupted | **Model** |
| Decomposition EN | "OTHER → Niloufar Ahmadi" for component-replacement impact | Questionable owner choice | Model; needs human review |
| org-reporting 0.5 | "Chief Executive Officer" instead of the name | Correct answer by role | **Kit**: gold too strict |
| scan-ocr / scan-qa | ۳۰ read as 20 | Digit misread on a degraded scan | **Model** |
| VRAM after-LVM / co-resident | Duplicate LVM, 3 models resident | Unload not verified | **Kit** bug (fixed) |

**Summary.** The real model errors are:
- 1 over-cautious refusal
- 1 wrong citation
- 2 Persian token corruptions
- missing WIN in Persian decomposition
- Persian name corruption
- a lenient summary judge
- a misread digit in Persian OCR

Kit defects caused the low cross-lingual score (0.79), half of the FA-20 penalty, the 15/20 summary score, the LVM org-reporting 0.5, and the invalid VRAM co-residency numbers.

## 8. Decisions

| Role | Model | Status | Reason |
|---|---|---|---|
| Embedding | bge-m3 | **selected (baseline)** | Passes MP-01 in every language mode with margin; strong FA↔EN alignment; ~13 ms per text; ~0.6 GB |
| LLM | qwen3:8b | **selected (baseline), with conditions** | ~58 tok/s on GPU; grounded QA 0.90–0.95; perfect refusal and JSON validity. Conditions: name/ID validation after generation, human review of decomposition, and a judge that is not trusted alone. |
| LVM | qwen2.5vl:3b | **selected for rendered images and tables; not for scanned Persian numbers** | 1.00 on rendered chart and table; misreads digits on scans. Scanned PDFs need an OCR step or a human check of numbers (decision for Phase 4). |

**Recommended defaults (think mode).**
- Thinking is **off by default** for QA, summaries, extraction, decomposition and judging. Thinking gave no measurable gain on 11 of 12 paired cases and costs 3–7× the latency.
- **Turn thinking on only as a retry:**
  - when think-off returns `INSUFFICIENT_CONTEXT` but retrieval found a high-scoring chunk (the FA-18 pattern), or
  - when a JSON output fails validation.
- Reconsider for Phase 10 judging once a human-agreement set exists.

**Other defaults.**
- `num_ctx` 8192 for qwen3 and the LVM; set `num_ctx` explicitly for bge-m3 too (kit 0.2.0 sends 8192).
- temperature 0.2 and seed 42 for evaluation.
- ~~Schema `format` gave no validity gain.~~ **Superseded by round 2 (section 11):** use schema `format` by default for decomposition and other structured JSON output.

**VRAM plan.**
- Keep **bge-m3 + qwen3:8b resident**: measured 7,496 MiB with no offload (run 192721).
- Load the LVM **on demand** for batch ingestion of visual documents, and unload it afterwards. With all three models loaded, the LVM is partly offloaded to the CPU (measured 11,347 MiB).
- Settings: `OLLAMA_MAX_LOADED_MODELS=2`, `keep_alive` `30m` for bge-m3 and qwen3 during work sessions and `0` for the LVM after a batch.
- Never measure VRAM without first verifying unload.

## 9. Limitations found

1. Persian generation sometimes corrupts tokens: mixed script ("دجANGO", "سation") and person names. Every name, ID and number in generated output must be validated against the source or registry in code (C-43).
2. The LLM judge is consistent on clear good/bad cases but lenient on subtle unsupported claims. With the new summary rubric it gave 20/20 to a Persian summary that still contains an unsupported claim (round 2). It is not valid for MP-03 without a human-agreement study (C-41, Phase 10).
3. Persian decomposition still sometimes misses a work stream (WIN in 1 of 3 Persian schema runs in round 2). Without schema `format`, 1 of 6 replies was malformed JSON.
4. Persian OCR on degraded scans misreads digits.
5. The test sets are small: 30 questions, 24 chunks, 4 judge cases, 3 images. Retrieval numbers are indicative only.
6. Batch embedding latency is anomalous (284 ms per chunk vs 13 ms single) and needs re-measurement.
7. All three models do not fit in 12 GiB together; the LVM spills to the CPU (measured).
8. C-17 is proven for the LLM stage only. Embedding and LVM use the same local Ollama server but were not run offline.
9. Thinking can run out of tokens: one think-on decomposition used all 2,048 tokens while still thinking and produced no answer.

## 10. Actions for later phases

| Phase | Action |
|---|---|
| 2 (close-out) | Done: `--only llm`, `--only vram` and an offline LLM run. Optional: one full offline run, `run_all.py` with the network off, to cover embedding and LVM under C-17. |
| 3 | Define `EmbeddingPort`, `LlmPort` and `LvmPort` plus a post-generation validator for names, IDs and numbers. Also add a claim check: numbers and durations in a summary must appear in the source. Use `strip_think` and `extract_json` from `common.py` (kit 0.2.1 rejects malformed outer JSON). |
| 4 | Route scanned PDFs through OCR or human verification of numbers. Use the LVM only for layout and rendered tables. |
| 5 | Chunk tables separately from narrative and prefix every chunk with document title and section, to fix the ISS-024 dilution. Consider stripping the company name from queries. |
| 8 | Evaluate MP-01 on the full chunked corpus. Add hybrid lexical search for IDs and names. Add the think-on retry rule. |
| 10 | Build the judge–human agreement set. Test whether a different judge model or think-on judging is less lenient. |
| 14 | Prompt tuning backlog: Persian decomposition (WIN coverage), exact name copying, Persian number formatting. |


## 11. Second round: confirmation runs

### 11.1 Offline run (C-17), `20261109-190709`

- Run on the same PC with the **internet disconnected**, using kit 0.1.0, LLM stage only (embedding and LVM not run).
- Result: 86/86 calls ok at 57.4 tok/s, with scores identical to run `20261109-184242`.
- **C-17 passes for the LLM stage.** Embedding and LVM go through the same local Ollama server but were not exercised offline.
- Only the console summary block was sent for this run, not the raw files, so it has no results folder.

### 11.2 Kit 0.2.0 LLM re-run, `20261109-191910` (`--only llm`)

Same models and seed as round 1. The new parts are prompt registry 0.2.0 (`issue.decompose` 1.1.0, `judge.summary` 1.0.0), data v1.1 and the fixed scoring. Raw files are in `results/20261109-191910/`; `rescored.json` there uses kit 0.2.1.

| Metric (think off) | Round 1 as-run | Round 1 rescored | **Round 2** | Phase 1 target |
|---|---|---|---|---|
| tok/s · TTFT p50 · wall p50 / p95 | 57.8 · 0.34 · 1.36 / 13.5 s | — | 57.0 · 0.35 · 1.37 / 17.24 s | — |
| QA FA fact / citation / false refusal | 0.93 / 0.90 / 0.05 | 0.95 / 0.90 / 0.05 | 0.95 / 0.90 / 0.05 | C-16 ≥ 0.90 |
| QA EN fact / citation / false refusal | 0.90 / 0.90 / 0.10 | 0.90 / 0.90 / 0.10 | **1.00 / 1.00 / 0.00** | C-16 ≥ 0.90 |
| QA cross (FA question, EN context) fact / citation | 0.79 / 1.00 | 0.917 / 1.00 | 0.92 / 1.00 | — |
| Refusal | 1.00 | 1.00 | 1.00 | — |
| Summaries fact rate / within word limit | 1.00 / 1.00 | 1.00 | 1.00 / 1.00 | — |
| Summary judge (4 summaries) | 15, 20, 20, 20 (QA rubric) | not rescorable | **20, 20, 20, 20** (`judge.summary`) | MP-03 ≥ 18/20 |
| Decompose prompt-only: JSON / schema valid | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 as-run; **0.83 rescored** / 0.83 | MP-08 100% |
| Decompose prompt-only: domain recall / coverage / exact names / n_sub | 0.72 / — / — / 5.0 | 0.72 / 0.83 / 0.97 / 5.0 | 0.83 / 0.83 / 1.00 / 4.33 | MP-04 |
| Decompose schema: JSON / schema valid | 1.00 / 1.00 | 1.00 / 1.00 | **1.00 / 1.00** | MP-08 100% |
| Decompose schema: domain recall / coverage / exact names / n_sub | 0.67 / — / — / 5.0 | 0.67 / 0.83 / 0.93 / 5.0 | **0.94 / 0.94 / 1.00 / 5.67** | MP-04 |
| Judge verdict accuracy (good / bad totals) | 1.00 (20 / 3–7) | 1.00 | 1.00 (20 / 4–7; EN-BAD-r1 = 6) | — |
| Think on: tok/s · first answer token · wall p50 / p95 · truncated | 56.7 · 5.94 · 7.53 / 20.97 s · 0 | — | 55.9 · 5.81 · 7.63 / 30.27 s · **1 of 12** | — |

**What the second round shows**

- **The fixes in data v1.1 worked.** EN-08 now passes, so the English results are 1.00 across the board. The cross-lingual score of 0.92 matches the round-1 rescore, which confirms that the 0.79 was a kit artefact.
- **Some model errors are deterministic.** Seed and temperature were the same, and these outputs repeated exactly:
  - FA-18 is still a false refusal with think off and is correct with think on.
  - FA-19 still cites `fa-LEG-009-c1`.
  - FA-15-cross still writes "دجANGO".
- **Decomposition prompt 1.1.0 plus schema `format` is the best setup.**
  - Domain recall rose to 0.94 from 0.67 in round 1. Persian names are now copied exactly (1.00). Persian WIN appears in 4 of 6 runs: one prompt-only run was malformed JSON and one schema run missed WIN. In round 1 it appeared in 0 of 6.
  - The gain comes from the prompt *and* schema mode together. With n = 3 per language, treat it as indicative.
  - Schema runs produce more sub-issues (5.67 vs 4.33). Whether that is over-splitting is not scored; human review in Phase 9/10 should check it.
- **A real model error the kit hid.** Prompt-only run `fa-prompt_only-r1` returned **malformed JSON**: a stray `" "` inside the fourth sub-issue.
  - Kit 0.2.0's fallback parser then returned the first inner sub-issue object, so the row was reported as `json_valid = true` but `schema_valid = false`.
  - Kit 0.2.1 parses only the outermost object and now reports it as invalid JSON. The prompt-only JSON-valid rate is therefore **0.83 in `rescored.json`**, not the 1.00 printed in the console. A unit test was added.
  - Schema mode (grammar-constrained) cannot produce this error.
- **The summary judge passes the threshold, but read that with care.**
  - All 4 summaries scored 20/20 with the new rubric, so the citation artefact from round 1 is gone.
  - However, the Persian executive summary is the **same text** as in round 1. It still contains "تأخیر ۲ ماه", which is not in any source chunk, and the garbled "تحویل سهمیه گزارش وب". The judge gave it a perfect score.
  - So MP-03 "passes" here only in the sense that the judge says so. The same model writes and judges, it misses unsupported claims, and the result must not be used as evidence of summary quality without the human check (C-41).
- **Think-on truncation.**
  - `decompose en-prompt_only-r0` with think on used all 2,048 tokens on 8,596 characters of thinking, so the answer was empty. That made the JSON invalid and the call took 37.4 s.
  - With think off, the same case was valid in 9.8 s. Thinking can make structured tasks worse, not just slower.

### 11.3 VRAM, `20261109-192721` (`--only vram`)

See section 6. Embedding + LLM co-resident: 7,496 MiB, fully on GPU. All three: 11,347 MiB, with the LVM partly offloaded to the CPU. Co-residency is no longer pending.

### 11.4 Decisions changed or confirmed by round 2

| Topic | Decision |
|---|---|
| Decomposition / structured JSON | **Schema `format` on by default**, with prompt `issue.decompose` 1.1.0: 1.00 valid, domain recall 0.94, vs 0.83 / 0.83 for prompt-only. Prompt-only stays a fallback, always with outer-object JSON validation. |
| Summary judge | `judge.summary` 1.0.0 is adopted. Its scores (4 × 20/20, so ≥ 18) are recorded as **judge-reported only**. MP-03 needs a human check and a code check that numbers and durations appear in the source. Same-model bias stays open. |
| Think mode | Still **off by default**. The think-on retry rule is confirmed for the FA-18 pattern. For think-on calls set `num_predict` ≥ 4096 (kit 0.2.1 default). If the model stops while still thinking (`done_reason = length` with an empty answer), retry with **think off + schema** instead of raising the budget again. Do not use think-on for decomposition. |
| Offline (C-17) | Passed for the LLM stage. |
| VRAM | Measured: bge-m3 + qwen3 resident at 7.3 GiB; LVM on demand, because three models together offload the LVM. |

## Appendix: raw files

`experiments/phase-02/results/20261109-184242/`:
- `results.json`
- `summary.md`
- `llm_runs.jsonl` (86 rows)
- `lvm_runs.jsonl` (7)
- `embedding_details.json`
- `rescored.json`, written by `tools/rescore.py` (regenerated with kit 0.2.1; values unchanged from 0.2.0)

The original zip sent by the user is `results/phase02-results-20261109-184242.zip`.

`experiments/phase-02/results/20261109-191910/`:
- `results.json`
- `summary.md`
- `llm_runs.jsonl` (86 rows)
- `rescored.json`, written with kit 0.2.1

Its zip is `results/phase02-results-20261109-191910.zip`.

Runs `20261109-190709` (offline) and `20261109-192721` (VRAM) were reported only as console summary blocks. Their numbers are transcribed in `results/round2-console-notes.md`.
