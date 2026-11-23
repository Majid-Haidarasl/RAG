# Phase 15 — Final checklist (release v0.9, "final trial core")

Every deliverable of the 16-phase plan and where it stands in kit 0.15.0. The same list is
machine-readable in `config/release-checklist.yaml`; `scripts/run_quality_check.py` loads it,
checks that every path of a `done` deliverable exists and prints one status per phase
(`checklist:` and `checklist_phases:` lines of the Phase 15 summary).

Statuses:

* **done** — in this kit; every listed path exists (checked on each run);
* **external** — delivered in its own repository folder (Phases 1–2 were planning kits made
  before the code base existed: `rag-phase-01`, `rag-phase-02`);
* **run** — produced by running the kit (results folders, the coverage report); the folder
  fills up on the first run;
* **planned** — a later step (the release tags and Phase 16).

Totals: 80 deliverables — done 57, external 12, run 3, planned 8.

## Per phase

| Phase | Topic | Deliverables | Status |
|---|---|---|---|
| 1 | Domain discovery & corpus | 8 | partial |
| 2 | Offline model baseline | 5 | external |
| 3 | DDD architecture & skeleton | 6 | done |
| 4 | Ingestion & chunking | 5 | done |
| 5 | Knowledge lifecycle & duplicates | 4 | done |
| 6 | Layer / node registry | 4 | done |
| 7 | Issues & sub-issues | 4 | done |
| 8 | Hybrid retrieval & node-scoped Q&A | 5 | done |
| 9 | Executors & IKE | 4 | done |
| 10 | Judge & rubric | 4 | done |
| 11 | Cyclic processing & knowledge transfer | 5 | done |
| 12 | Project tracking & key issues | 5 | done |
| 13 | RFP & proposals | 5 | done |
| 14 | Prompt testing & model tuning | 5 | done |
| 15 | Unit-test completion & hardening | 4 | partial |
| 16 | Final wrap-up | 7 | planned |

Phase 1 is `partial` because its planning documents live in `rag-phase-01` and only the corpus is part of
this kit. Phase 15 is `partial` only because its release tag is still planned (see below).

## All deliverables

| Phase | Deliverable | Status | Where in the kit | Note |
|---|---|---|---|---|
| 1 | docs/phase-01/domain-discovery.md | external | — | repository folder rag-phase-01 (planning kit before the code base) |
| 1 | docs/phase-01/glossary.md | external | — | repository folder rag-phase-01 |
| 1 | docs/phase-01/bounded-contexts-draft.md | external | — | repository folder rag-phase-01 |
| 1 | data/registry/layer-registry.template.csv | external | — | repository folder rag-phase-01; the filled registry is the Phase 6 data/registry/layer-registry.csv |
| 1 | data/registry/node-registry.template.csv | external | — | repository folder rag-phase-01; the filled registry is the Phase 6 data/registry/node-registry.csv |
| 1 | docs/phase-01/evaluation-baseline.md | external | — | repository folder rag-phase-01 |
| 1 | docs/phase-01/unit-test-policy.md | external | — | repository folder rag-phase-01 |
| 1 | corpus/README.md (26 FA + 26 EN ArmanRayan docs + manifest) | done | `corpus/README.md`, `corpus/manifest.md`, `corpus/fa`, `corpus/en` |  |
| 2 | docs/phase-02/offline-model-baseline.md | external | — | repository folder rag-phase-02 |
| 2 | docs/phase-02/model-usage-guide.md | external | — | repository folder rag-phase-02 |
| 2 | docs/phase-02/prompt-test-plan.md | external | — | repository folder rag-phase-02 |
| 2 | config/model-registry.yaml | external | — | repository folder rag-phase-02; the kit's model settings live in config/rag.yaml and config/judge.yaml |
| 2 | experiments/phase-02/ (sample prompt runs + results) | external | — | repository folder rag-phase-02 |
| 3 | docs/phase-03/ddd-architecture.md | done | `docs/phase-03/ddd-architecture.md` |  |
| 3 | docs/phase-03/domain-model-spec.md | done | `docs/phase-03/domain-model-spec.md` |  |
| 3 | docs/phase-03/context-map.md | done | `docs/phase-03/context-map.md` |  |
| 3 | docs/phase-03/unit-test-plan.md | done | `docs/phase-03/unit-test-plan.md` |  |
| 3 | src/ project skeleton (one package per bounded context) | done | `src/rag_core/__init__.py`, `src/rag_core/shared_kernel` |  |
| 3 | tests/ skeleton + pytest config | done | `tests/unit`, `pyproject.toml` |  |
| 4 | src/ingestion/ (DOC/DOCX/PDF adapters) | done | `src/rag_core/ingestion/infrastructure/parser_docx.py`, `src/rag_core/ingestion/infrastructure/dispatcher.py` |  |
| 4 | docs/phase-04/metadata-schema.md + schemas/knowledge-metadata.json | done | `docs/phase-04/metadata-schema.md`, `schemas/knowledge-metadata.json` |  |
| 4 | docs/phase-04/source-reference-model.md | done | `docs/phase-04/source-reference-model.md` |  |
| 4 | docs/phase-04/chunking-spec.md | done | `docs/phase-04/chunking-spec.md` |  |
| 4 | tests/unit/ingestion/ | done | `tests/unit/ingestion` |  |
| 5 | src/knowledge/lifecycle/ (KnowledgeItem, KnowledgeVersion, KnowledgeChunk) | done | `src/rag_core/knowledge/domain/model.py`, `src/rag_core/knowledge/domain/services.py` |  |
| 5 | src/knowledge/dedup/ (exact, near-duplicate, overlap) | done | `src/rag_core/knowledge/domain/dedup.py`, `src/rag_core/knowledge/domain/fingerprint.py` |  |
| 5 | docs/phase-05/versioning-and-dedup.md | done | `docs/phase-05/versioning-and-dedup.md` |  |
| 5 | tests/unit/knowledge/ (version, chunk, dedup rules) | done | `tests/unit/knowledge` |  |
| 6 | src/organization/ (Node, Layer, hierarchy) | done | `src/rag_core/hierarchy/domain/model.py`, `src/rag_core/hierarchy/domain/scope.py` |  |
| 6 | data/registry/layer-registry.csv + node-registry.csv (ArmanRayan L0–L4) | done | `data/registry/layer-registry.csv`, `data/registry/node-registry.csv` |  |
| 6 | docs/phase-06/hierarchy-workflows.md | done | `docs/phase-06/hierarchy-workflows.md` |  |
| 6 | tests/unit/organization/ | done | `tests/unit/hierarchy` | the organization context is named hierarchy in the code |
| 7 | src/issues/ (Issue, SubIssue, status) | done | `src/rag_core/issues/domain/model.py` |  |
| 7 | src/issues/comparison.py | done | `src/rag_core/issues/comparison.py` |  |
| 7 | docs/phase-07/issue-model.md (Azarpakhsh case as reference) | done | `docs/phase-07/issue-model.md` |  |
| 7 | tests/unit/issues/ | done | `tests/unit/issues` |  |
| 8 | src/rag/ (embedding adapter, index, retriever, context assembler) | done | `src/rag_core/rag/domain/retriever.py`, `src/rag_core/rag/domain/context.py`, `src/rag_core/rag/infrastructure/sqlite_store.py` |  |
| 8 | src/qa/ (node-scoped Q&A + citations) | done | `src/rag_core/qa/application/service.py`, `src/rag_core/qa/domain/fact_check.py` |  |
| 8 | config/prompts/qa/*.yaml | done | `config/prompts/qa/answer.yaml` |  |
| 8 | docs/phase-08/rag-pipeline.md | done | `docs/phase-08/rag-pipeline.md` |  |
| 8 | tests/unit/rag/ (retrieval orchestration, prompt assembly) | done | `tests/unit/rag`, `tests/unit/qa` |  |
| 9 | src/executors/ (profiles, expertise, matching) | done | `src/rag_core/executors/domain/expertise.py` |  |
| 9 | src/ike/ (relations + summary generation) | done | `src/rag_core/ike` |  |
| 9 | docs/phase-09/ike-model.md | done | `docs/phase-09/ike-model.md` |  |
| 9 | tests/unit/executors/ + tests/unit/ike/ | done | `tests/unit/executors`, `tests/unit/ike` |  |
| 10 | src/judge/ (rubric, parser, threshold) | done | `src/rag_core/judging/domain/rubric.py`, `src/rag_core/judging/domain/parser.py`, `src/rag_core/judging/domain/threshold.py` | the context is named judging in the code |
| 10 | config/prompts/judge/*.yaml | done | `config/prompts/judge/rubric.yaml`, `config/prompts/judge/qa.yaml` |  |
| 10 | docs/phase-10/scoring-framework.md | done | `docs/phase-10/scoring-framework.md` |  |
| 10 | tests/unit/judge/ (score parsing, thresholds) | done | `tests/unit/judge` |  |
| 11 | src/processing/ (cyclic node processing) | done | `src/rag_core/processing/domain/cycle.py` |  |
| 11 | src/transfer/ (TransferPackage, detail levels) | done | `src/rag_core/transfer` |  |
| 11 | exports/transfer-packages/*.csv + DB persistence | run | `exports/transfer-packages` | written by scripts/run_transfer_check.py; the folder is not committed |
| 11 | docs/phase-11/transfer-workflow.md | done | `docs/phase-11/transfer-workflow.md` |  |
| 11 | tests/unit/transfer/ | done | `tests/unit/transfer` |  |
| 12 | src/projects/ | done | `src/rag_core/projects` |  |
| 12 | src/research_gaps/ | done | `src/rag_core/research_gaps` |  |
| 12 | src/prioritization/ | done | `src/rag_core/prioritization` |  |
| 12 | docs/phase-12/project-knowledge.md | done | `docs/phase-12/project-knowledge.md` |  |
| 12 | tests/unit/projects/ + research_gaps/ + prioritization/ | done | `tests/unit/projects`, `tests/unit/research_gaps`, `tests/unit/prioritization` |  |
| 13 | src/rfp/ (generator) | done | `src/rag_core/rfp/domain/generator.py` |  |
| 13 | src/proposals/ (registry, evaluation, feedback) | done | `src/rag_core/proposals` |  |
| 13 | config/prompts/rfp/*.yaml | done | `config/prompts/rfp/rfp_summary.yaml`, `config/prompts/rfp/feedback.yaml` |  |
| 13 | docs/phase-13/rfp-and-evaluation.md | done | `docs/phase-13/rfp-and-evaluation.md` |  |
| 13 | tests/unit/rfp/ + proposals/ | done | `tests/unit/rfp`, `tests/unit/proposals` |  |
| 14 | docs/phase-14/model-and-prompt-evaluation.md | done | `docs/phase-14/model-and-prompt-evaluation.md` |  |
| 14 | config/prompts/ (tuned set) | done | `config/prompts/qa/answer_complete.yaml`, `config/prompts/judge_strict`, `config/prompts/rfp_ids` |  |
| 14 | eval/datasets/armanrayan-qa.jsonl (FA + EN questions) | done | `eval/datasets/armanrayan-qa.jsonl` |  |
| 14 | eval/results/ | run | `eval/results` | phase-14-check-*.json and updated-metrics-*.md per run; only the README is committed |
| 14 | docs/phase-14/updated-metrics.md | done | `docs/phase-14/updated-metrics.md` |  |
| 15 | docs/phase-15/unit-test-report.md | done | `docs/phase-15/unit-test-report.md` |  |
| 15 | coverage report | run | `results/phase-15` | coverage.json / coverage.txt / htmlcov written by scripts/setup_and_test.sh; not committed |
| 15 | release tag v0.9 (final trial core) | **set** | git tag `v0.9` | set on the pushed Phase 15 commit after the reference run passed; `config/release-checklist.yaml` kept `planned` because the check ran before the tag existed |
| 15 | docs/phase-15/final-checklist.md | done | `docs/phase-15/final-checklist.md` |  |
| 16 | README.md + docs/technical/ | planned | — | Phase 16 (final wrap-up) |
| 16 | docs/user-guide.md | planned | — | Phase 16 |
| 16 | docs/final-report.md | planned | — | Phase 16 |
| 16 | eval/evidence/ | planned | — | Phase 16 |
| 16 | presentation/ (slides + demo script) | planned | — | Phase 16 |
| 16 | training/ (learning material) | planned | — | Phase 16 |
| 16 | release tag v1.0 | planned | — | Phase 16, after the final run |

## Release tag plan

* **v0.9 — final trial core.** The Phase 15 run on the target system (20261123T215647Z UTC,
  about 01:26 Tehran time on 3 Azar 1405) printed `status: PASS` with all 11 checks ok and
  `readiness: ready=yes`. The Phase 15 commit is pushed and the annotated tag `v0.9` is set on
  exactly that pushed commit. The one live advisory, `disagrees:ai_ids=baseline`, is listed in
  the release notes and does not block the tag (see `unit-test-report.md`, section 6).
* **v1.0.** Phase 16, after the final run and the final documents.

## Run results

| Item | Value |
|---|---|
| `checklist:` line | `deliverables=80 done=57 external=12 run=3 planned=8 phases=16 problems=0` |
| `checklist_phases:` line | `1=partial 2=external 3=done … 14=done 15=partial 16=planned` (3–14 all done) |
| `release:` line | `tag=v0.9 (final trial core) not tagged yet; tag the pushed Phase 15 commit after this PASS docs=2/2` (printed before the tag was set; `v0.9` is set now) |
| Status | PASS, 1643 tests passed, line coverage 96.3 %, branch coverage 89.6 % |
| Tag | `v0.9` set on the pushed Phase 15 commit after this PASS |

## Open items for Phase 16

* Decide `ai_ids` in `config/eval.yaml`: Phase 15's live run measured `baseline` better than
  `listed_guarded` (accepted 2/4 vs 1/4, named ids 11/18 vs 9/18, though `listed_guarded`
  invented 0 ids). Most likely switch to `baseline`, or keep the guard for safety.
* All Phase 16 deliverables above (`planned`).
