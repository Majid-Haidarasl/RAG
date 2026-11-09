# Phase 2 offline model baseline — run 20261109-191910

- Kit 0.2.0 | mode: FULL | total 6.54 min
- Ollama 0.40.2 | Python 3.12.3 | GPU NVIDIA GeForce RTX 3060
- Models: embedding=bge-m3:latest, llm=qwen3:8b, lvm=qwen2.5vl:3b

## Embedding (bge-m3)

- skipped: 

## LLM (qwen3:8b)

- calls 86 | ok 86 | errors 0

| think | n | tok/s | TTFT p50 s | first answer token p50 s | wall p50 s | wall p95 s | out tokens | truncated |
|---|---|---|---|---|---|---|---|---|
| think_off | 74 | 57.0 | 0.35 | 0.35 | 1.37 | 17.24 | 177 | 0.00 |
| think_on | 12 | 55.9 | 0.17 | 5.81 | 7.63 | 30.27 | 588 | 0.08 |

| quality (think off) | values |
|---|---|
| qa_mono_fa | n=20, fact_rate_mean=0.95, all_facts_rate=0.95, citation_ok_rate=0.90, citation_precision_mean=0.90, false_refusal_rate=0.05 |
| qa_mono_en | n=10, fact_rate_mean=1.00, all_facts_rate=1.00, citation_ok_rate=1.00, citation_precision_mean=1.00, false_refusal_rate=0.00 |
| qa_cross_fa | n=12, fact_rate_mean=0.92, all_facts_rate=0.92, citation_ok_rate=1.00, citation_precision_mean=1.00, false_refusal_rate=0.00 |
| refusal | n=4, correct_refusal_rate=1.00, exact_token_rate=1.00 |
| summary_executive | n=2, fact_rate_mean=1.00, words_mean=55.50, within_limit_rate=1.00 |
| summary_technical | n=2, fact_rate_mean=1.00, words_mean=108.50, within_limit_rate=1.00 |
| decompose_prompt_only | n=6, json_valid_rate=1.00, schema_valid_rate=0.83, domain_recall_mean=0.83, executor_match_mean=0.83, executor_coverage_mean=0.83, executor_name_exact_mean=1.00, n_sub_issues_mean=4.33 |
| decompose_schema | n=6, json_valid_rate=1.00, schema_valid_rate=1.00, domain_recall_mean=0.94, executor_match_mean=0.94, executor_coverage_mean=0.94, executor_name_exact_mean=1.00, n_sub_issues_mean=5.67 |
| judge | n=8, json_valid_rate=1.00, schema_valid_rate=1.00, sum_consistent_rate=1.00, verdict_accuracy=1.00, totals={'JDG-FA-GOOD-r0': 20, 'JDG-FA-GOOD-r1': 20, 'JDG-FA-BAD-r0': 7, 'JDG-FA-BAD-r1': 7, 'JDG-EN-GOOD-r0': 20, 'JDG-EN-GOOD-r1': 20, 'JDG-EN-BAD-r0': 4, 'JDG-EN-BAD-r1': 6} |
| judge_on_summaries | SUM-fa-executive-r0=20, SUM-fa-technical-r0=20, SUM-en-executive-r0=20, SUM-en-technical-r0=20 |

| think on vs off | metric | off | on | wall off→on s | tokens off→on |
|---|---|---|---|---|---|
| qa FA-09-mono | fact_rate | 1.00 | 1.00 | 1.5→4.7 | 59→254 |
| qa FA-18-mono | fact_rate | 0.00 | 1.00 | 1.4→8.5 | 50→461 |
| qa FA-20-mono | fact_rate | 1.00 | 1.00 | 1.2→7.1 | 41→388 |
| qa EN-03-mono | fact_rate | 1.00 | 1.00 | 1.0→3.3 | 32→178 |
| qa EN-07-mono | fact_rate | 1.00 | 1.00 | 1.0→5.2 | 34→286 |
| qa FA-09-cross | fact_rate | 1.00 | 1.00 | 1.4→5.8 | 56→321 |
| refusal REF-FA-02 | refused | True | True | 0.9→5.0 | 40→275 |
| summary fa-executive | fact_rate | 1.00 | 1.00 | 4.3→10.0 | 215→554 |
| decompose fa-prompt_only-r0 | schema_valid | True | True | 18.1→24.5 | 977→1339 |
| decompose en-prompt_only-r0 | schema_valid | True | False | 9.8→37.4 | 524→2048 |
| judge JDG-FA-BAD-r0 | verdict_correct | True | True | 1.6→9.0 | 86→497 |
| judge JDG-EN-BAD-r0 | verdict_correct | True | True | 2.5→8.1 | 138→454 |

## LVM (qwen2.5vl:3b)

- skipped: 

## VRAM

- before: no model loaded | 588 MiB used
- after-llm: qwen3:8b 6004MB/6004MB ctx=8192 | 6763 MiB used
- peak during llm: 6763 MiB, util 100%
