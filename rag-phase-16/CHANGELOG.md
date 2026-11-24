# Changelog

All versions of rag-core, newest first. Phase N of the plan shipped as version 0.N.0;
Phases 1 and 2 were planning kits in their own folders (`rag-phase-01`, `rag-phase-02`).

## [1.0.0] — 1405-09-03, Phase 16, release

- Release check `scripts/run_release_check.py` with `config/release.yaml`: one version everywhere,
  release documents complete, phrase scan of every text file, slide deck, evidence of the run,
  changelog, checklist and the evaluation defaults. New tests in `tests/unit/release/`.
- `config/eval.yaml`: `ai_ids` back to `baseline`, as measured in the Phase 15 run (2/4 accepted,
  0 invented ids, against 1/4 for `listed_guarded`). `listed_guarded` stays as a variant.
- Checklist: every deliverable is done; only the `v1.0` tag is left. A phase whose items are
  done here or delivered in their own folder now counts as `done`.
- New documents: `README.md`, `docs/user-guide.md`, `docs/final-report.md`, `docs/technical/`,
  `docs/phase-16/final-checklist.md`, `eval/evidence/`, `presentation/`, `training/`.
- Install guide for Ubuntu and Windows 11 (WSL 2).
- Final run: 1715 tests passed, line coverage 96.3 %, branch coverage 89.8 %, every phase PASS; tag `v1.0`.
- Presentation redesigned after the release: 15 slides edited in PowerPoint (font B Nazanin);
  `presentation/build_slides.js` keeps the earlier 12-slide draft. The deck check now allows 10-15 slides.
- Cleaner output: every summary block now starts with `======== PHASE N SUMMARY ========`;
  the run notes in the READMEs and scripts were shortened and made consistent.

## [0.15.0] — 1405-09-03, Phase 15, unit-test completion and hardening

- 150 new tests for edge cases and error paths; coverage with pytest-cov and a gate of 80 %.
- Three small fixes found by those tests; fact pre-check in front of the strict judge
  (`strict_precheck`) and the invented-id guard (`listed_guarded`).
- Release checklist `config/release-checklist.yaml`; tag `v0.9` (final trial core).
- Reference run: 1643 tests passed, line coverage 96.3 %, branch coverage 89.6 %.

## [0.14.0] — Phase 14, prompt testing and model tuning

- Bilingual gold set (16 pairs, 32 items), ranking metrics, judge agreement and a selection
  rule with tie-breakers; variants for retrieval, QA prompt, judge prompt and required ids.
- `config/eval.yaml` and `docs/phase-14/updated-metrics.md`.

## [0.13.0] — Phase 13, RFPs and proposals

- RFP blueprints, validation and grounding; proposal registry, weighted evaluation, decision
  check and feedback; AI texts checked for required ids.

## [0.12.0] — Phase 12, project tracking and key issues

- Projects, achievements, challenges, research gaps, unsolved issues and a scorecard;
  weighted key-issue priority with a sensitivity check.

## [0.11.0] — Phase 11, cyclic processing and knowledge transfer

- Bottom-up cycle over the hierarchy, TransferPackage generation with detail levels,
  review, suggestions and CSV export.

## [0.10.0] — Phase 10, judge and rubric

- Rubric, score parser, thresholds, a rule judge and an LLM judge; calibration set of 14 cases.

## [0.9.0] — Phase 9, executors and IKE

- Executor profiles, expertise, capacity and matching; issue-knowledge relations and summaries.

## [0.8.0] — Phase 8, hybrid retrieval and node-scoped Q&A

- SQLite index, BM25 + embedding retrieval, context assembly, answers with citations and a fact check.

## [0.7.0] — Phase 7, issues and sub-issues

- Issue / sub-issue model, status, comparison with knowledge and decomposition.

## [0.6.0] — Phase 6, layer and node registry

- Layers L0–L4 and nodes of ArmanRayan, workflows and retrieval scope.

## [0.5.0] — Phase 5, knowledge lifecycle and duplicates

- KnowledgeItem / Version / Chunk lifecycle; exact, near-duplicate and overlap detection.

## [0.4.0] — Phase 4, ingestion and chunking

- DOCX / DOC / PDF parsers, metadata schema, source references and chunking.

## [0.3.0] — Phase 3, DDD architecture

- Bounded contexts, domain model, context map, unit-test plan and the project skeleton.
