# Phase 3 — Unit-Test Plan

Status: v1.0. Date: 10 November 2026.
Policy: `docs/phase-01/unit-test-policy.md`. This plan says which policy items are already executable on the Phase 3 skeleton, and which wait for later phases.

## 1. Tooling (unchanged)

- Python ≥ 3.12, `pytest`, optional `pytest-cov`.
- No network, no GPU, no Ollama, no corpus file I/O.
- Layout:

```
tests/
  unit/<context>/test_*.py
  fakes/models.py          # FakeEmbeddingModel, FakeLlm, FakeLvm, FakeJudge
  fixtures/armanrayan.py   # 5 layers and a handful of nodes, in memory
```

- Names follow `test_<unit>_<condition>_<expected_result>`.
- Markers: `@pytest.mark.<context>` plus `shared_kernel`.

Run: `bash scripts/setup_and_test.sh` or `pytest -q`. A single context: `pytest -q -m hierarchy`.

## 2. Policy items vs this phase

| # | Policy item | Phase 3 tests | Later work |
|---|---|---|---|
| 1 | Register `N-SW-WEB` layer 3, parent `N-SW` | `test_registering_web_team_…` | CSV load of all 21 nodes (Phase 6) |
| 2 | Parent–child validation | same layer, missing parent, self-parent, leaf, L4 exemption | Longer cycle after a reparent API, if added |
| 3 | Knowledge metadata | missing subject domain rejected | Broader metadata record in Phase 4 |
| 4 | Versioning v1.0 → v1.1 | `test_updating_creates_v1_1_…` | Persistence |
| 5 | Chunk boundaries | heading path and order kept | Real chunker (Phase 5) |
| 6 | Duplicate / overlap / FA–EN | hash exact, overlap, cross-language pair | Near-duplicate threshold with embeddings |
| 7 | Issue creation | empty title rejected | — |
| 8 | Sub-issue relation | `AR-ISS-024/WIN` parent + position 2 | — |
| 9 | Progress 0–100 | all resolved → 100; mean of 80 and 40 → 60 | Richer formula if the supervisor defines one |
| 10 | Priority stability | identical inputs, stable id tie-break | — |
| 11 | Executor matching | domain filter; Roozbeh alias | Full 15-profile registry |
| 12 | L0 TransferPackage fields | risks, decisions, citations required | Cyclic processing orchestration |
| 13 | Judge 17 fail / 18 pass / bad JSON | `test_score_17_of_20_…` | Real judge adapter + C-41 study |
| 14 | Prompt assembly with citations | `test_template_plus_context_…` | Full prompt registry from Phase 2 JSON |
| 15 | RFP needs criteria | `test_rfp_without_criteria_…` | — |
| 16 | 60/40 → 78.8 and 75.2 | `test_sixty_forty_weights_…` | Replace reconstructed components if the corpus table differs |
| 17 | CSV Persian round-trip | `test_csv_round_trip_keeps_persian_text` | Persistent package store |
| 18 | In-memory vs CSV repository contract | In-memory only | Phase 6 |

Additional tests (not numbered in the policy): shared-kernel numerals and identifiers (D1, Arabic comma), SimilarityScore bounds, IKE uniqueness / knowledge-lack event, node-boundary drop + abstention, Phase 2 baseline model names, fake embedding determinism, `FactValidationReport` helpers.

## 3. Definition of done for this phase

- `pytest -q` is green offline on the student's Ubuntu machine.
- Each invariant that is already encoded in an aggregate has a passing and a failing-input example (or a rejected construction).
- Model ports are only used through fakes.
- No test reads `corpus/` or opens a socket.

Coverage of the current skeleton was 83% of `rag_core` on the author's machine (Protocol-only modules pull the figure down; domain models sit roughly 86–95%). The 80% target in the policy remains the target for *finished* domain and application modules, not a gate on empty ports.

## 4. Out of scope (reminded)

Integration, e2e, load, security and UX tests. Real-model evaluation (MP / C metrics) stays in the Phase 2 experiment kit and later evaluation phases.
