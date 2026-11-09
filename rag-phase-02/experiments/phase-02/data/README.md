# Phase 2 test data

All facts come from the ArmanRayan corpus (`corpus/fa`, `corpus/en`, version v1.0) and `shared-facts.md`. Nothing is invented.

| File | Content |
|---|---|
| `chunks.jsonl` | 24 chunks: 12 topics × FA/EN. They are verbatim paragraphs and table rows from AR-ORG-001, HR-004, HR-005, HR-006, FIN-008, LEG-009, HW-012, HW-014, SW-016, SW-022, ISS-024 and RFP-025. `source_lines` gives the paragraph/table-row index in the extracted DOCX text. |
| `gold_questions.jsonl` | 30 questions: 20 FA and 10 EN. Each has its relevant chunk IDs in both languages, `expected_facts` as groups of alternatives, and `cross_lingual_facts`, the language-neutral facts used when an FA question is answered from EN context. A unit test checks that every expected fact appears in its relevant chunk. |
| `llm_cases.json` | Refusal cases (answer absent from context), AR-ISS-024 decomposition input with expected domains and executors, summary sources and facts, and judge cases (good and deliberately wrong answers). |
| `images/` | `org_chart.png` (FA+EN), `revenue_table.png` (AR-FIN-008 numbers), `scanned_sla_fa.png` (AR-SW-022 table, rotated, noisy, JPEG-degraded). `images.json` holds the prompts and expected names and numbers. |

Fact matching normalizes Persian/Arabic digits, thousands separators (`٬` `,`), the decimal `٫`, ZWNJ and Arabic ي/ك, then does a case-insensitive substring match.

## Data v1.1 (after run 20261109-184242)

- FA-20 also accepts "الف".
- EN-08 was reworded because the RFP ID it cited was not in the chunk.
- RAM facts also accept "حافظه" and "memory".
- org-reporting also accepts "Chief Executive Officer" and "مدیرعامل".
- `llm_cases.json` gained `allowed_executors` for the exact-name check.

Chunks are unchanged, so retrieval numbers stay comparable.
