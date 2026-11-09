# Phase 2 offline model baseline — run 20261109-184242

- Kit 0.1.0 | mode: FULL | total 7.16 min
- Ollama 0.40.2 | Python 3.12.3 | GPU NVIDIA GeForce RTX 3060
- Models: embedding=bge-m3:latest, llm=qwen3:8b, lvm=qwen2.5vl:3b

## Embedding (bge-m3)

- dim 1024 | cold first call 11.20 s | single-text latency mean 13.10 ms | batch 283.61 ms/chunk

| mode | n | R@1 | R@3 | R@5 | MRR | MP-01 (R@5≥0.80, MRR≥0.60) |
|---|---|---|---|---|---|---|
| fa | 20 | 0.85 | 0.95 | 0.95 | 0.91 | pass |
| en | 10 | 0.90 | 0.90 | 1.00 | 0.93 | pass |
| cross_fa2en | 20 | 0.90 | 0.95 | 0.95 | 0.93 | pass |
| cross_en2fa | 10 | 0.90 | 1.00 | 1.00 | 0.95 | pass |
| mixed | 30 | 0.87 | 0.93 | 0.97 | 0.91 | pass |

- FA↔EN parallel-chunk cosine 0.827 vs non-parallel 0.462 (gap 0.366)

## LLM (qwen3:8b)

- calls 86 | ok 86 | errors 0

| think | n | tok/s | TTFT p50 s | first answer token p50 s | wall p50 s | wall p95 s | out tokens | truncated |
|---|---|---|---|---|---|---|---|---|
| think_off | 74 | 57.8 | 0.34 | 0.34 | 1.36 | 13.50 | 161 | 0.00 |
| think_on | 12 | 56.7 | 0.17 | 5.94 | 7.53 | 20.97 | 506 | 0.00 |

| quality (think off) | values |
|---|---|
| qa_mono_fa | n=20, fact_rate_mean=0.93, all_facts_rate=0.90, citation_ok_rate=0.90, citation_precision_mean=0.90, false_refusal_rate=0.05 |
| qa_mono_en | n=10, fact_rate_mean=0.90, all_facts_rate=0.90, citation_ok_rate=0.90, citation_precision_mean=0.90, false_refusal_rate=0.10 |
| qa_cross_fa | n=12, fact_rate_mean=0.79, all_facts_rate=0.75, citation_ok_rate=1.00, citation_precision_mean=1.00, false_refusal_rate=0.00 |
| refusal | n=4, correct_refusal_rate=1.00, exact_token_rate=1.00 |
| summary_executive | n=2, fact_rate_mean=0.83, words_mean=55.50, within_limit_rate=1.00 |
| summary_technical | n=2, fact_rate_mean=1.00, words_mean=108.50, within_limit_rate=1.00 |
| decompose_prompt_only | n=6, json_valid_rate=1.00, schema_valid_rate=1.00, domain_recall_mean=0.72, executor_match_mean=0.72, n_sub_issues_mean=5.00 |
| decompose_schema | n=6, json_valid_rate=1.00, schema_valid_rate=1.00, domain_recall_mean=0.67, executor_match_mean=0.67, n_sub_issues_mean=5.00 |
| judge | n=8, json_valid_rate=1.00, schema_valid_rate=1.00, sum_consistent_rate=1.00, verdict_accuracy=1.00, totals={'JDG-FA-GOOD-r0': 20, 'JDG-FA-GOOD-r1': 20, 'JDG-FA-BAD-r0': 7, 'JDG-FA-BAD-r1': 7, 'JDG-EN-GOOD-r0': 20, 'JDG-EN-GOOD-r1': 20, 'JDG-EN-BAD-r0': 4, 'JDG-EN-BAD-r1': 3} |
| judge_on_summaries | SUM-fa-executive-r0=15, SUM-fa-technical-r0=20, SUM-en-executive-r0=20, SUM-en-technical-r0=20 |

| think on vs off | metric | off | on | wall off→on s | tokens off→on |
|---|---|---|---|---|---|
| qa FA-09-mono | fact_rate | 1.00 | 1.00 | 1.5→5.9 | 59→254 |
| qa FA-18-mono | fact_rate | 0.00 | 1.00 | 1.3→8.4 | 50→461 |
| qa FA-20-mono | fact_rate | 0.50 | 0.50 | 1.2→7.0 | 41→388 |
| qa EN-03-mono | fact_rate | 1.00 | 1.00 | 1.0→3.3 | 32→178 |
| qa EN-07-mono | fact_rate | 1.00 | 1.00 | 1.0→5.2 | 34→286 |
| qa FA-09-cross | fact_rate | 1.00 | 0.00 | 1.4→5.8 | 56→321 |
| refusal REF-FA-02 | refused | True | True | 0.9→4.9 | 40→275 |
| summary fa-executive | fact_rate | 1.00 | 1.00 | 4.3→9.9 | 215→554 |
| decompose fa-prompt_only-r0 | schema_valid | True | True | 13.1→26.0 | 719→1448 |
| decompose en-prompt_only-r0 | schema_valid | True | True | 9.9→16.9 | 549→950 |
| judge JDG-FA-BAD-r0 | verdict_correct | True | True | 1.6→8.9 | 86→497 |
| judge JDG-EN-BAD-r0 | verdict_correct | True | True | 2.4→8.0 | 138→454 |

## LVM (qwen2.5vl:3b)

- score mean 0.85 | wall p50 2.50 s | tok/s 107.4 | prompt tokens/image ≈ 1360

| task | score | wall s | missing |
|---|---|---|---|
| org-extract | 1.00 | 24.9 |  |
| org-reporting | 0.50 | 3.4 | arash moradi |
| org-fa-question | 1.00 | 0.1 |  |
| table-extract | 1.00 | 2.5 |  |
| table-qa | 1.00 | 0.3 |  |
| scan-ocr | 0.92 | 3.2 | 30 |
| scan-qa | 0.50 | 0.2 | 30 min |

## VRAM

- before: no model loaded | 490 MiB used
- after-embed: bge-m3:latest 633MB/633MB ctx=4096 | 1322 MiB used
- after-llm: qwen3:8b 6004MB/6004MB ctx=8192 | 6711 MiB used
- after-lvm: qwen2.5vl:3b 2997MB/2997MB ctx=8192; qwen2.5vl:3b 2997MB/2997MB ctx=8192 | 9396 MiB used
- co-resident embed+llm: qwen3:8b 5015MB/6270MB ctx=8192; bge-m3:latest 633MB/633MB ctx=4096; qwen2.5vl:3b 2997MB/2997MB ctx=8192 | 10891 MiB used
- peak during embed: 1335 MiB, util 57%
- peak during llm: 6711 MiB, util 100%
- peak during lvm: 9396 MiB, util 100%
- peak during co-resident: 9777 MiB, util 15%
