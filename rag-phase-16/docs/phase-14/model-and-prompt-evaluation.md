# Phase 14 — Prompt testing, model tuning and sample evaluation

Kit version 0.14.0 (GitHub issue #14). Phase 14 adds a **bilingual gold set** of question/answer pairs, compares **retrieval variants**, **Q&A prompt variants**, **judge prompt variants** and **required-id prompt variants** against it, and records which variant is chosen and why. It answers the open findings of the earlier phases:

| Finding | Phase | Phase 14 answer |
|---|---|---|
| The Q06 answer ("causes of the Azarpakhsh delay") found 2 of 3 facts | 8 | `context_facts` metric (did the facts reach the prompt at all?), the `wide` retrieval variant, the `qa.answer_complete` prompt with a list rule, and gold pair P06 with all four causes |
| The LLM judge was lenient (near-all 20/20, accepted P8-Q06, `CAL-N03`, `CAL-N06`; kappa 0.0 on key outputs) | 10 | a strict judge prompt with a **fact checklist** and score caps, and a calibration set grown from 14 to **42** cases |
| AI texts dropped required ids (English RFP summary 2/4, feedback 1/2) | 11–13 | id-list prompt variants: a numbered **REQUIRED IDS** list, and the same with **one retry** that names the missing ids |

There are no new dependencies. Unit tests never need Ollama, the GPU or the internet. The code runs on Python 3.12 to 3.15.

Target system: Fedora Linux, Python 3.15.2, Ollama 0.40.17, project at `~/Desktop/RAG`.

## 1. Where things live

Issue #14 asks for prompt testing, model tuning and sample evaluation. They form a new bounded context `tuning` inside `rag_core`; it only talks to the other contexts through anti-corruption layers.

| Issue #14 output | Code / file |
|---|---|
| evaluation dataset (FA + EN) | `eval/datasets/armanrayan-qa.jsonl`; model and validation `tuning/domain/gold.py`; reader `tuning/infrastructure/gold_jsonl.py` |
| metrics | `tuning/domain/metrics.py` (hit@k, MRR, context facts, agreement / kappa / leniency, p95, detail level) |
| variant choice | `tuning/domain/variants.py` (`Candidate`, `SelectionRule`, `pick`, `selection_problems`); `config/eval.yaml` |
| required ids | `tuning/domain/required_ids.py` (checklist, missing ids, retry note, run summary) |
| comparisons | `tuning/application/services.py` (`compare_retrieval`, `judge_report`, `summarize_prompt`, `IdVariantRunner`, `choose`) |
| ACLs | `tuning/infrastructure/rag_acl.py` (Phase 8 retrieval and Q&A, corpus grounding, scope), `judging_acl.py` (Phase 10 cases, derived calibration, strict prompts), `ids_acl.py` (Phase 13 results) |
| tuned prompt set | `config/prompts/qa/answer_complete.yaml`, `config/prompts/judge_strict/`, `config/prompts/rfp_ids/` |
| run + summary | `scripts/run_eval_check.py` (called last by `scripts/setup_and_test.sh`) |
| results | `eval/results/` (JSON + Markdown per run; not committed, see its README) |
| measured numbers | `docs/phase-14/updated-metrics.md` |
| tests | `tests/unit/tuning/test_tuning_*.py` (markers `tuning`, `eval_gold`, `eval_metrics`); helpers `tests/fixtures/tuning/samples.py` |

The baseline prompts stay where they were (`config/prompts/qa/answer.yaml`, `config/prompts/judge/`, `config/prompts/rfp/`), so Phases 8–13 behave exactly as before. The strict judge prompts live in their own folder because the Phase 10 loader requires each output kind to be covered once per folder.

## 2. Gold set

`eval/datasets/armanrayan-qa.jsonl` holds **16 pairs = 32 items**, one JSON object per line. A pair is the same question in Persian and English, asked from the same node.

| Pair | Source | Node | Status | Documents | Facts | Detail |
|---|---|---|---|---|---|---|
| P01 | Phase 8 Q01 | N-SW-SUP | answered | AR-SW-022 | Priority 1: 30 / 4 | short |
| P02 | Q02 | N-SW-SUP | answered | AR-SW-022 | Priority 2: 2 / 16 | short |
| P03 | Q03 | N-ADM-HR | answered | AR-HR-005 | hourly leave: 4 / 16 | short |
| P04 | Q04 | N-HW-REP | answered | AR-HW-012 | Level 1 repair: 4 | short |
| P05 | Q05 | N-CEO | answered | AR-ISS-024 | hardware amendment ceiling: 95 | short |
| P06 | Q06 | N-SW-WEB | answered | AR-ISS-024 | **4** causes: RAID, memory, Windows client, web reporting | list |
| P07 | Q07 | N-ADM-FIN | answered | AR-FIN-010 | advance payment: 30% / 654 | short |
| P08 | Q08 | N-SW-WEB | answered | AR-RFP-025 | weighted scores: 78.8 / 75.2 | short |
| P09 | Q09 | N-SW-WEB | out_of_scope | outside: AR-HR-005 | escalate to N-CEO | refusal |
| P10 | Q10 | N-CEO | not_found | – | – | refusal |
| P11 | new | N-ADM-HR | answered | AR-HR-004 | vacancy advertisement: 10 days | short |
| P12 | new | N-ADM-HR | answered | AR-HR-006 | raise approval: 15% / 25% | short |
| P13 | new | N-ADM-LEG | answered | AR-LEG-009 | contract approval: 500 / 2,000 | short |
| P14 | new | N-HW-ASM | answered | AR-HW-015 | delivery minutes: serials, exceptions, signer Ehsan Davari, customer | list |
| P15 | new | N-CEO | answered | AR-ISS-024 | Rouzbeh Mohseni, AR-SW-019, AR-ISS-024/WIN | short |
| P16 | new | N-CEO | answered | AR-ISS-024 | closure evidence: hardware configuration, software scope, delivery date | list |

Fields per item: `id`, `pair`, `language`, `node`, `question`, `expected_status`, `expected_docs`, `expected_outside_docs`, `expected_escalation`, `expected_facts` (groups of acceptable alternatives), `evidence` (document, language, verbatim quote), `reference_answer`, `partial_answer`, `detail` (`short` ≤ 3 sentences, `list` ≤ 6, `refusal` ≤ 2) and `origin` (`phase8:Q0x` or `phase14`). In a reference label `[AR-ISS-024 §2]`, `§2` is the **second evidence quote** of the item, not a section of the document.

Every item is checked twice:

1. **Validation** (`validate_gold`, no corpus needed): facts in the quotes and in the reference, labels point at a quote, the reference and the question are in the item's language, the partial answer keeps at most half of the facts and has a label, refusals carry no facts, start with `INSUFFICIENT_CONTEXT` and name an escalation when out of scope, and both languages of a pair agree on status, documents, detail and number of facts.
2. **Grounding** (`gold_grounding`, real corpus): every quote is found in its document (after the Phase 5 normalisation: digits, yeh/kaf, ZWNJ, punctuation), every fact group is in the quotes, and the reference and partial answers contain no number or id that is not in the quotes. **Scope**: answered items see their documents from their node, out-of-scope items do not, and the Phase 6 route escalates to the expected node.

All ten Phase 8 sample questions are covered (`phase8=10/10`).

## 3. Retrieval variants

| Variant | top_k | candidates | BM25 weight | vector weight | context budget (tokens) |
|---|---|---|---|---|---|
| `baseline` (Phase 8) | 5 | 30 | 1.0 | 1.0 | 3500 |
| `wide` | 8 | 40 | 1.0 | 1.0 | 5000 |
| `lexical_boost` | 5 | 30 | 1.5 | 1.0 | 3500 |
| `wide_lexical` | 8 | 40 | 1.5 | 1.0 | 5000 |

Metrics over the 28 answered items: **hit@1/3/5** (an expected document among the first k distinct documents), **MRR** (mean of 1/rank of the first expected document) and **context facts** (the share of expected fact groups present in the assembled context the model would see). A fact missing from the answer while present in the context is a generation problem; missing from the context, a retrieval problem. The Q06 line in the summary shows rank and context facts of P06 for each variant.

Offline, only BM25 runs, so the two weighted variants rank like their unweighted twins; the weights matter in the live hybrid run (BM25 + `bge-m3`, Reciprocal Rank Fusion). Raising `top_k` alone does not help if the context budget is already full, so `wide` also raises the budget to 5000 tokens (fits `num_ctx` 8192 of `qwen3:8b`).

## 4. Q&A prompt variants

`qa.answer@2.0.0` (Phase 8) and `qa.answer_complete@3.0.0`. The new prompt keeps every Phase 8 rule (scope, labels, refusal token) and adds:

- a **detail rule**: for a question that asks for causes, steps or items, name every item that the sources give, one short sentence each; for a single value, one or two sentences;
- a **sub-issue id rule**: copy ids such as `AR-ISS-024/WIN` exactly when the sources give them;
- at most 6 sentences;
- a **self-check** line in the user prompt (every fact has a label, no fact outside the sources).

Live, both prompts answer all 32 items with the retrieval variant chosen in `config/eval.yaml`. Measured per prompt: status correct, facts found, grounded answers, citation validity, rule-judge acceptance (Phase 10 rubric), detail level kept, mean and p95 generation time.

## 5. Judge prompt variants and the 42-case calibration set

The Phase 10 calibration set has 14 hand-labelled cases. Phase 14 derives **28 more** from the gold set: for every answered pair one **reference answer** (gold accept) in one language and one **broken answer** (gold reject) in the other language. The broken answer rotates over five mutations so every kind is covered:

| Mutation | What changes | Rule that should reject it |
|---|---|---|
| `drop_fact` | the partial answer (≤ half the facts) | correctness / completeness |
| `wrong_number` | the last number becomes one not in the sources | grounding |
| `wrong_language` | the reference of the other language | clarity (language) |
| `fake_label` | every label points at a decoy document (AR-HR-011 or AR-HR-004) | citation |
| `refuse_answerable` | `INSUFFICIENT_CONTEXT` although the sources answer | correctness |

Offline, the rule judge must accept all 14 references and reject all 14 broken answers; on the 14 Phase 10 cases it may only miss the known blind spot `CAL-N06`.

The **strict judge** (`judge.qa.strict@2.0.0`, `judge.summary.strict@2.0.0`) works in two steps. Step 1 ticks a numbered **CHECKLIST**, filled by `ChecklistJudgePrompt` from the case: one line per reference fact group (answers), the refusal / escalation behaviour (refusals) or one line per required id (summaries), plus "every number and id is in the sources" and the language. Step 2 ties the scores to the checklist: one line "no" caps correctness at 3 and completeness at 1, two or more cap them at 2 and 0; an unsupported number caps grounding at 2; a wrong or missing label caps citation; a wrong language gives clarity 0; a refusal of an answerable question gives correctness 0.

Live, the baseline and the strict prompt judge all 42 cases with `qwen3:8b` (think off, JSON). Measured per prompt: agreement with gold, Cohen's kappa, **leniency** (share of gold rejects that were accepted), false rejects, rejection per mutation kind, errors and time per case.

## 6. Required-id variants

The four Phase 13 AI-text jobs (RFP summary and runner-up feedback, Persian and English) are read from the newest `results/phase-13/rfp-check-*.json`, which the setup script writes just before Phase 14.

| Variant | Prompt |
|---|---|
| `baseline` | Phase 13 prompt (`config/prompts/rfp/`): ids as one comma-separated line after the facts |
| `listed` | `config/prompts/rfp_ids/`: numbered **REQUIRED IDS** list before the facts, an `ids_used` key and a check sentence |
| `listed_retry` | `listed` plus one retry when an id is missing; the retry note names the missing ids (`retry_note`) and the better of the two texts is kept |

Measured per variant: ids named, texts with all ids, grounded texts, invented ids, rule-judge acceptance, retries and time. An AI text is accepted only when it is grounded, invents no id and the rule judge accepts it.

## 7. Choosing a variant

`config/eval.yaml` → `selection` holds the chosen variant per kind with a written reason (the reasons are printed in the JSON). `selection_rules` say how the script ranks its own measurements: a primary metric, tie-breakers and a minimum gain over the baseline ("a change has to earn its place").

| Kind | Configured | Rule (primary, then tie-breakers) | Reason in short | Measured on my system |
|---|---|---|---|---|
| retrieval | `wide` | context facts, hit@5, MRR; min gain 0.02 | Q06's causes sit in two chunks; more room for the second | **`baseline`** (`agrees=NO`) |
| qa_prompt | `qa.answer_complete` | facts, rule accept, generation time; 0.02 | list rule aimed at Q06 | **`qa.answer`** (`agrees=NO`) |
| judge_prompt | `strict` | accuracy, leniency (lower), time; 0.02 | Phase 10 leniency | `strict` (`agrees=yes`) |
| ai_ids | `listed_retry` | accept rate, mention rate, time; 0 | Phase 11–13 missing ids | `listed_retry` (`agrees=yes`) |
| generation_model | `qwen3:8b` | – | the installed model; fits 12 GB with `bge-m3` | not compared |
| embedding_model | `bge-m3:latest` | – | multilingual; reuses the Phase 8 index | not compared |

The summary prints one `choice:` line per measured kind with the configured variant, the measured winner and `agrees=yes/NO`. A `NO` does not fail the run; it means the configuration should be revisited with the measured numbers (`docs/phase-14/updated-metrics.md`). The checked rule is that every kind is chosen, the variant exists and the reason is written.

**Two of the four configured choices disagreed with the reference run** (§10). `config/eval.yaml` and the code are kept exactly as they were tested; the defaults are switched to `baseline` and `qa.answer` in Phase 15 and verified again on the target system.

More generation models can be compared by adding installed models to `live.generation_models`; each extra model answers the 32 gold items with every Q&A prompt (within `live.max_generations`).

## 8. Checks

`pytest`, `prior_steps` (all ten earlier steps exit 0, including `rfp`), `gold_loaded`, `gold_valid`, `gold_grounded`, `gold_in_scope`, `phase8_covered`, `retrieval_offline` (every variant scores all 28 answered items, no scope violation), `calibration_expanded` (42 cases, all five mutation kinds, rule judge as described in §5), `prompts_render` (baseline and strict judge prompts on all 42 cases, both Q&A prompts), `ids_controls` (prompt rendering, missing-id detection, retry notes and the retry loop with a fake model) and `selection_documented`. The live step is advisory and never changes PASS/FAIL.

## 9. Live step and runtime

Needs `qwen3:8b` and `bge-m3` in the local Ollama. Calls: about 32 query embeddings (cached across the four retrieval variants), 64 answers (2 prompts × 32), 84 judge calls (2 prompts × 42) and 12–16 AI texts. Caps: `live.max_generations` 120 and `live.max_judge_calls` 100. The exact times are printed in `live_timings`. On my system the live part took about **6 minutes** (retrieval 5.4 s, Q&A 179.1 s, judges 97.9 s, required ids 83.6 s), faster than the 10–15 minutes estimated beforehand.

## 10. Results on my system

Reference run: 3 Azar 1405, about 00:30 Tehran time (results file `eval/results/phase-14-check-20261123T210037Z.json`), on Fedora Linux with Python 3.15.2 and Ollama 0.40.17 (`qwen3:8b` + `bge-m3`, think off). Result: **PASS**, 1493 tests passed, all 12 checks `ok`, live step `ok`. The full tables are in `docs/phase-14/updated-metrics.md`.

| Finding | Before | Phase 14 measurement |
|---|---|---|
| Q06 facts | 2 of 3 (Phase 8) | **4 of 4** in Persian and English with both Q&A prompts; all four causes reach the context with every retrieval variant |
| LLM judge leniency | accepted P8-Q06, `CAL-N03`, `CAL-N06` (Phase 10) | baseline prompt: 7 false accepts of 20 gold rejects (leniency 0.350, kappa 0.661); **strict prompt: 4 false accepts (leniency 0.200, kappa 0.712)**, 2 false rejects |
| Missing required ids | English RFP summary 2/4, feedback 1/2 (Phase 13) | baseline 11/18 ids named; **`listed_retry` 15/18**, all ids in 3 of 4 texts, but 1 invented id and still 2/4 accepted |

**Retrieval.** Offline (BM25 only) all four variants rank identically: hit@1 0.857, hit@3 0.893, hit@5 0.929, MRR 0.884, context facts 62/62. Live (hybrid), `baseline` and `wide` are identical (hit@5 0.929, MRR 0.833); `wide_lexical` has the best MRR (0.846) and `lexical_boost` loses the English Q06 document from the top 5 (hit@5 0.893). Every variant already puts all 62 fact groups in the context, so the primary metric ties and no variant beats `baseline` by the minimum gain of 0.02. The measured choice is `baseline`; the bigger context of `wide` costs prompt length and buys nothing on this gold set.

**Q&A prompt.** `qa.answer` found 62/62 facts, status 32/32, rule judge 28/28; `qa.answer_complete` found 60/62, status 31/32, rule judge 26/28 and was slightly slower (2.76 s vs 2.67 s average). Both gave all 4 Q06 causes. So in this run the Phase 8 prompt already names all four Q06 causes when they are in the context; the list rule was not needed, and the extra rules cost two facts and one status elsewhere. The measured choice is `qa.answer`.

**Judge prompt.** Both prompts caught every `fake_label` (3/3) and `wrong_number` (2/2) case and 3/4 `wrong_language` cases. The strict prompt fixed `refuse_answerable` (0/2 → 2/2) and was faster (1.06 s vs 1.27 s per case). **`drop_fact` is still weak: 1 of 3 caught with either prompt**, so the checklist does not yet make `qwen3:8b` reject an answer that leaves out a fact. The rule judge stays the stronger check (41/42, kappa 0.952; only `CAL-N06` missed). `strict` is kept (accuracy 0.857 vs 0.833).

**Required ids.** `listed` alone was worse than `baseline` (9/18 ids, 1/4 accepted, 1 invented). The retry did the work: `listed_retry` retried 3 texts and reached 15/18 ids and all ids in 3/4 texts, but invented 1 id, so acceptance stayed at 2/4 and the time per text rose from 5.2 s to 9.65 s. It wins only on the tie-breaker (mention rate). AI texts stay advisory, as in Phase 13.

## 11. Limitations

- 16 pairs are enough to see large effects (Q06, leniency, missing ids) but not small ones; one changed answer moves a metric by about 3–4 points.
- The derived calibration cases are built from the gold references, so they test whether a judge notices clear faults, not subtle reasoning errors. The swapped-number blind spot (`CAL-N06`) is still only in the Phase 10 set.
- The strict judge is still `qwen3:8b`, the same model as the writer; a different judge model would be a stronger check.
- Offline retrieval uses BM25 only; the vector weight only matters in the live run.
- The four retrieval variants hardly differ on 28 answered items, because the context already holds every fact; a harder gold set (more list questions, more similar documents) is needed to separate them.
- Generation is deterministic only as far as Ollama is (`seed` 42, temperature 0.2); small run-to-run differences are possible.
