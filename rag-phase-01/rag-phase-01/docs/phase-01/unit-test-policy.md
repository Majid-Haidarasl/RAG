# Phase 1 — Unit-Test Policy

Status: approved approach for the project, version 0.1 (supervisor may adjust targets). Source: specification section 18 and section 4.2.

## 1. Principle

Software evaluation in this project is **limited to unit tests**. Tests target domain logic and the deterministic behaviour of application services. Anything that needs a real model, a real file system tree, a network or a user interface is either replaced by a deterministic test double or is out of scope.

## 2. In scope (spec 18.1)

| # | Area | Context | Example test (ArmanRayan data) |
|---|---|---|---|
| 1 | Node and layer creation rules | Hierarchy | Registering `N-SW-WEB` with layer 3 and parent `N-SW` succeeds |
| 2 | Parent–child validation | Hierarchy | Parent on the same layer, missing parent, or a cycle is rejected |
| 3 | Knowledge metadata validation | Knowledge | KnowledgeItem without node ID or confidentiality is rejected |
| 4 | Knowledge versioning rules | Knowledge | Updating AR-HW-012 creates v1.1 active, v1.0 kept and inactive |
| 5 | Chunking boundary rules | Knowledge | Chunks of AR-ORG-002 keep document ID, version, heading path and order |
| 6 | Duplicate and overlap logic | Knowledge | Same hash → exact duplicate; FA/EN pair → not duplicate |
| 7 | Issue creation rules | Issues | Issue without title or owning node is rejected |
| 8 | Sub-issue relation rules | Issues | AR-ISS-024/WIN has parent AR-ISS-024 and position 2 |
| 9 | Progress calculation | Issues | Fixed inputs give the same `ProgressPercentage`; value always 0–100 |
| 10 | Issue priority calculation | Issues | Ranking is stable for identical input |
| 11 | Executor matching rules | Executors | Candidate outside the allowed referral domain is excluded |
| 12 | TransferPackage assembly rules | Transfer | L0 package contains risks, decisions requested and source references |
| 13 | Judge score parsing and threshold | Judging | 17/20 → fail; 18/20 → pass; malformed JSON → parse error |
| 14 | Prompt assembly logic | Model & Prompt | Template + context produce the expected prompt, citations included |
| 15 | RFP structure rules | RFP | RFP without evaluation criteria fails validation |
| 16 | Proposal rubric application | RFP | 60/40 weights reproduce 78.8 and 75.2 for AR-RFP-025 bids |
| 17 | CSV output formatting | Transfer | Package round-trips through CSV with Persian text intact |
| 18 | Repositories with test doubles | All | `InMemoryNodeRepository` satisfies the same contract as the CSV repository |

## 3. Out of scope (spec 18.2)

Integration tests, end-to-end tests, browser tests, load tests, security/penetration tests and automated user-experience evaluation are **not** part of the project. Model quality is measured separately through the evaluation sets in `evaluation-baseline.md`, not through the unit-test suite.

## 4. Tooling

- Language: Python 3.11+.
- Runner: `pytest`; coverage with `pytest-cov`.
- No network, no GPU, no real model weights during tests. A test that tries to open a socket fails.
- File access only through pytest's `tmp_path` fixture; corpus files are not read by unit tests — small synthetic fixtures based on corpus facts are used instead.
- Target runtime: whole suite under 2 minutes on a laptop.

## 5. Deterministic test doubles for models

| Port | Fake | Behaviour |
|---|---|---|
| `EmbeddingPort` | `FakeEmbeddingModel` | Vector derived from a hash of normalized text; same text → same vector; dimension fixed (e.g., 8) |
| `LlmPort` | `FakeLlm` | Returns scripted responses keyed by prompt template ID; records received prompts for assertions |
| `JudgePort` | `FakeJudge` | Returns a configured `JudgeScore` (e.g., 18 or 17) to test pass/fail branches |
| `LvmPort` | `FakeLvm` | Returns fixed layout text for a flagged document |
| Repositories | `InMemory*Repository` | Dict-based storage implementing the repository interface |
| Clock / IDs | `FixedClock`, `SequentialIdGenerator` | Deterministic timestamps and identifiers |

Real-model behaviour may be checked at unit level only with fixed sample outputs captured once from the local model and stored as fixtures (spec 18.2).

## 6. Layout and naming

```
tests/
  unit/
    hierarchy/test_node.py
    knowledge/test_versioning.py
    issues/test_progress.py
    ...
  fakes/        # deterministic doubles shared by all tests
  fixtures/     # small synthetic data derived from ArmanRayan facts
```

- File: `test_<module>.py`, mirroring `src/<context>/<module>.py`.
- Test function: `test_<unit>_<condition>_<expected_result>`, e.g. `test_issue_progress_all_subissues_resolved_returns_100`.
- Structure: Arrange / Act / Assert, one behaviour per test.
- Markers: `@pytest.mark.<context>` (e.g. `hierarchy`, `judging`) to run one context.

## 7. Rules

1. Every domain rule written in phases 3–13 ships with at least one passing and one failing-input test.
2. A bug fix starts with a test that reproduces it.
3. Tests do not depend on order or shared mutable state.
4. Test data uses fictional ArmanRayan facts only; no real personal data.
5. Coverage target (initial, pending supervisor review): ≥ 80% line coverage of the domain and application layers; adapters for real models are excluded from coverage.

## 8. Definition of done for a module

- Unit tests pass offline (`pytest -q`).
- Each invariant listed in the module's aggregate has a test.
- Model-dependent logic uses a port and is tested with a fake.
- Test names read as behaviour specifications in the ubiquitous language (`glossary.md`).
