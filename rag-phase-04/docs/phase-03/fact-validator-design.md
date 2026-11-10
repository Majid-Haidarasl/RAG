# Phase 3 — Fact Validator Design

Status: v1.0 design. **Implementation of the verifier is deferred to Phase 8.** Date: 10 November 2026.
Related: Phase 2 model-usage-guide (think policy), model-registry conditions (“post-generation validation of person names, document IDs and numbers against source/registry”), data-quality findings D1 and D2.

## 1. Why this service exists

Local LLM output is useful for wording and structure, but it is not a source of record. In Phase 2, `qwen3:8b`:

- sometimes corrupted Persian person names (decomposition executor-name exact match < 1.0);
- is not trusted for identifiers or quantities even when overall fact rates were high;
- is judged separately from source text, and the judge itself once accepted an unsupported “۲ ماه” claim.

The project rule is therefore: **after generation, names, identifiers and numbers in the output are checked in code against the retrieved source (and, where relevant, against the node / executor / document registries).** The model does not get a second chance to “remember” a number. Think mode is only a retry for a false abstention (FA-18), not a substitute for this check.

## 2. Placement

| Piece | Location | Status in Phase 3 |
|---|---|---|
| Digit and number normalization | `rag_core.shared_kernel.numerals` | Implemented and unit-tested |
| Identifier normalization (`AR-FIN-۰۰۸` → `AR-FIN-008`) | `DocumentId`, `IssueId`, … | Implemented and unit-tested |
| Person-name alias table (Roozbeh / Rouzbeh) | `executors.domain.model.canonical_person_name` | Implemented and unit-tested |
| `FactValidator` protocol and report types | `rag_core.shared_kernel.fact_ports` | Contract only |
| Claim extraction + matching against sources | Knowledge / shared domain service | Phase 8 |
| Integration after `LlmPort.complete` in RAG, Transfer, Issues, RFP | Application services | Phase 8 |

The protocol lives in the shared kernel so several contexts can depend on one contract without importing Knowledge. The implementation will be allowed to read source chunk text and registry snapshots through explicit arguments, not by reaching into other aggregates.

## 3. Claims in scope

| `FactKind` | Examples from the corpus | Normalized form |
|---|---|---|
| `PERSON_NAME` | Roozbeh Mohseni, روزبه محسنی, Dr. Nima Yazdani | Canonical Latin or Persian form plus alias list |
| `DOCUMENT_ID` | `AR-FIN-۰۰۸`, `AR-ISS-024`, `AR-CNT-1402-118` | Latin digits, uppercase, `DocumentId` / `IssueId` rules |
| `NODE_ID` | `N-SW-WEB` | `NodeIdentifier` |
| `ISSUE_ID` | `AR-ISS-024/WIN` | `IssueId` |
| `NUMBER` | 62%, 30 minutes, 15%, 26 days | `Decimal` after grouping marks are removed |
| `MONEY` | ۲٬۱۸۰ million toman, 78.8, 95M | `Decimal` in the stated unit; unit kept as metadata |
| `DATE` | 12 Esfand 1402, 20 Mehr 1403 | A later calendar value object; not implemented now |

Out of scope for the validator (handled elsewhere): citation *presence* (RAG invariant), judge threshold, semantic faithfulness of free prose beyond extractable facts.

## 4. Normalization rules (stable now)

These are already code, not just a plan.

1. **Digits.** Persian `۰–۹` (U+06F0–U+06F9) and Arabic-Indic `٠–٩` (U+0660–U+0669) map to Latin `0–9` before an identifier or number is parsed. Display may keep the original span.
2. **Thousands separators**, stripped when they appear as grouping marks:
   - Western comma `,`
   - Arabic thousands separator `٬` (U+066C)
   - Arabic comma `،` (U+060C) — Phase 2 scoring missed this
   - underscore, space, NBSP, thin space, narrow NBSP
3. **Decimal separators.** `.` and Arabic decimal `٫` (U+066B). A second decimal mark is an error.
4. **Document ids** in eight Persian corpus files use Persian digits (finding D1). `DocumentId("AR-FIN-۰۰۸")` stores `AR-FIN-008`. File rewrite is still planned for Phase 4; the value object already tolerates the noise.
5. **Person names.** Registry spelling is `Roozbeh Mohseni`. `Rouzbeh Mohseni` is an alias (finding D2), not a second person.

## 5. Algorithm (Phase 8)

```
validate(generated_text, source_texts, source_document_ids?, registries?) -> FactValidationReport
  1. Extract claims (names, ids, numbers, money, dates) from generated_text.
  2. Normalize each claim (section 4).
  3. For each claim, search normalized source_texts and, if provided, the
     node / executor / document registries.
  4. Assign a verdict:
       CONFIRMED    exact normalized match in a cited source or registry
       CORRECTED    unique close match (alias, digit shape, thousands mark);
                    record the replacement
       FLAGGED      ambiguous (two people, two amounts) — do not guess
       UNSUPPORTED  no evidence; the calling use case must not publish the claim
  5. Never invent a “better” name or number that is not in the source or registry.
```

Calling rules for application services (to be wired in Phase 8):

- A grounded RAG answer with any `UNSUPPORTED` money, id or name is either repaired with a `CORRECTED` value, stripped of that claim, or turned into an abstention.
- A structured decomposition (schema mode) is rejected or sent to human review if an executor name is `UNSUPPORTED`.
- The LLM judge is not the fact validator. A 20/20 judge score does not override an `UNSUPPORTED` numeric claim (lesson from the Phase 2 summary-judge miss).

## 6. Test plan for Phase 8 (not executed now)

| Case | Expected |
|---|---|
| Output `AR-FIN-۰۰۸`, source `AR-FIN-008` | `CORRECTED` |
| Output `۲٬۱۸۰`, source `2,180 million toman` | `CONFIRMED` |
| Output `2،180` (Arabic comma) | `CONFIRMED` against 2180 |
| Output `Rouzbeh Mohseni`, registry `Roozbeh Mohseni` | `CORRECTED` |
| Output `علی محمدی` with no source mention | `UNSUPPORTED` |
| Output `95M` when the source says “proposed, not approved” | still a present number — confirmation of the amount; *approval status* is a separate prose/judge concern, with a trap question in the evaluation set (finding D5) |

Phase 3 already covers the normalization rows through `tests/unit/shared_kernel/test_numerals.py`, `test_identifiers.py` and the executor alias test.
