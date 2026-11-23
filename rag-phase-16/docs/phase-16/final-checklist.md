# Phase 16 — Final checklist (release 1.0.0)

Every deliverable of the 16-phase plan and where it stands in kit 1.0.0. The machine-readable list is
`config/release-checklist.yaml`; `scripts/run_quality_check.py` and `scripts/run_release_check.py` load it,
check that every path of a `done` deliverable exists and print one status per phase. This file replaces
`docs/phase-15/final-checklist.md`, which stays as the record of release v0.9.

Statuses:

* **done** — in this kit; every listed path exists (checked on each run);
* **external** — delivered in its own repository folder (`rag-phase-01`, `rag-phase-02`) or in git (the `v0.9` tag);
* **run** — produced by running the kit (results folders, the coverage report);
* **planned** — not yet done when the check runs: only the release tag v1.0. The check runs before the tag
  can exist, so the file keeps it as `planned`; the tag was set after the final run passed (see below).

Totals: 80 deliverables — done 63, external 13, run 3, planned 1.

A phase is `done` when nothing is left to do in it: its items are done or run here, or delivered in their own
folder. Phase 2 is `external` (all of it lives in `rag-phase-02`); Phase 16 is `partial` until the v1.0 tag is set.

## Per phase

| Phase | Topic | Deliverables | Status |
|---|---|---|---|
| 1 | Domain discovery & corpus | 8 | done |
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
| 15 | Unit-test completion & hardening | 4 | done |
| 16 | Final wrap-up | 7 | partial in the run; done after the v1.0 tag |

## All deliverables

| Phase | Deliverable | Status | Where | Note |
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
| 15 | release tag v0.9 (final trial core) | external | — | git tag v0.9 on the Phase 15 commit of the repository |
| 15 | docs/phase-15/final-checklist.md | done | `docs/phase-15/final-checklist.md` |  |
| 16 | README.md + docs/technical/ | done | `README.md`, `docs/technical/README.md`, `docs/technical/architecture.md`, `docs/technical/operations.md` |  |
| 16 | docs/user-guide.md | done | `docs/user-guide.md` |  |
| 16 | docs/final-report.md | done | `docs/final-report.md`, `docs/phase-16/final-checklist.md`, `CHANGELOG.md` |  |
| 16 | eval/evidence/ | done | `eval/evidence/README.md` |  |
| 16 | presentation/ (slides + demo script) | done | `presentation/armanrayan-rag-core.pptx`, `presentation/build_slides.js`, `presentation/demo-script.md` |  |
| 16 | training/ (learning material) | done | `training/README.md`, `training/exercises.md` |  |
| 16 | release tag v1.0 | planned → **set** | git tag `v1.0` | set on the pushed Phase 16 commit after the final run passed |

## Release tags

* **v0.9 — final trial core.** Set on the Phase 15 commit after the Phase 15 run passed (3 Azar 1405).
* **v1.0 — first release.** Set on the Phase 16 commit after the final run printed `status: PASS` in the
  PHASE 16 SUMMARY (3 Azar 1405).

## Final run

Run of 20261123T224140Z (UTC), about 02:11 Tehran time on 3 Azar 1405, Python 3.15.2, Ollama 0.40.17.
Every phase from 4 to 16 printed `status: PASS`.

| Item | Value |
|---|---|
| `checklist:` line | `deliverables=80 done=63 external=13 run=3 planned=1 phases=16 problems=0` |
| `checklist_phases:` line | `1=done 2=external 3=done … 15=done 16=partial` (3–15 all done) |
| Tests | 1715 passed, 0 failed (59.23 s) |
| Coverage | line 96.3 % (13977/14509), branch 89.8 % (3595/4002), 292 modules |
| Release check | `status: PASS`, 12/12 checks ok, `readiness: ready=yes live_confirmed=4/4` |
| Results file | `results/phase-16/release-check-20261123T224140Z.json` |
| Tag | `v1.0` (first release) set on the pushed Phase 16 commit |
