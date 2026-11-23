# Phase 15 — Unit-test report

Kit version 0.15.0 (GitHub issue #15, "Unit-test completion & hardening"). This report covers
how the unit tests are measured, which tests were added, which defects they found, and what the
first run on the target system printed.

Target system: Fedora Linux, Python 3.15.2, Ollama 0.40.17,
project at `~/Desktop/RAG`.

## 1. What Phase 15 adds

| Issue #15 item | Where |
|---|---|
| Complete unit tests of the core modules (edge cases, error paths, input validation) | `tests/unit/hardening/` (marker `hardening`), `tests/unit/quality/` (marker `quality`), `tests/unit/tuning/test_tuning_carryover.py` (marker `carryover`) |
| Fix domain-logic defects | `shared_kernel/numerals.py`, `shared_kernel/language.py`, `rag/infrastructure/config.py` (section 4) |
| Validate the deterministic workflows | every earlier phase check still runs in `scripts/setup_and_test.sh`; their exits are the `prior_steps` of Phase 15 |
| Validate the CSV / DB workflows | the CSV registry (Phase 6), the CSV exports (Phases 11–13) and the SQLite stores (Phases 8 and 11) keep their own tests and run in the earlier phase checks; the coverage report shows their modules line by line |
| Coverage report | `results/phase-15/coverage.json`, `coverage.txt`, `htmlcov/index.html` |
| Release readiness | `config/release-checklist.yaml`, `docs/phase-15/final-checklist.md`, `scripts/run_quality_check.py` |

A new bounded context `rag_core.quality` holds the coverage arithmetic, the coverage gate, the
release checklist model and a static test inventory. It reads coverage.py's JSON output through
an infrastructure reader; the domain itself does only arithmetic and never imports coverage.py.

## 2. How coverage is measured

* **Tool.** coverage.py through pytest-cov. Both were already listed as development
  dependencies (`pytest-cov>=5.0`; `coverage>=7.6` is now listed explicitly), so nothing new is
  downloaded. The setup script installs them into `.venv` with the rest of `.[dev]`. When pip
  cannot reach the network but the venv already works, the script prints a NOTE and goes on.
* **What is measured.** `src/rag_core` only (`--cov=rag_core`). Tests and scripts are not part
  of the number. Branch coverage is on (`[tool.coverage.run] branch = true`).
* **Excluded lines.** Only `if TYPE_CHECKING:`, `raise NotImplementedError` and protocol stubs
  (`...` bodies). Nothing else is hidden.
* **Outputs** (folder `results/phase-15/`, ignored by git):
  `coverage.json` (read by the quality check), `coverage.txt` (the text table),
  `htmlcov/index.html` (open in a browser; red lines were never run).
* **Without pytest-cov.** The tests still run; the summary prints `coverage: missing` and the
  checks `coverage_measured` and `coverage_gate` fail.

### The gate

`config/quality.yaml` → `coverage.min_line_pct: 80`. The gate passes when the **total line
coverage of `src/rag_core`** is at least 80 %. Per-context numbers are printed but not gated
(`min_context_pct: 0`).

Why 80: the core contexts are pure Python with many small unit tests, so the estimate before
the first run was 85–90 %. The parts that cannot run without Ollama (HTTP clients, the live
steps) and the parsers for `.doc` / `.pdf` that need external tools are the expected low
modules. 80 leaves room for them without letting a large untested module slip through. The
estimate was not measured before shipping; if the first run lands under 80 % the gate fails
honestly and the summary lists the ten least covered modules (`coverage_lowest`).

## 3. New tests

| Area | File | Tests (pytest count) | What they pin down |
|---|---|---|---|
| Numerals | `hardening/test_hardening_numerals.py` | 15 | Persian / Arabic-Indic digits, every thousands separator, decimal separators, rejection of `NaN`, `Infinity`, `1e5`, `1.2.3` |
| Identifiers | `hardening/test_hardening_identifiers.py` | 26 | node, document, issue / sub-issue, executor, project, RFP and knowledge-item ids; layer index range and type; language aliases and bad input; error hierarchy |
| Persian text | `hardening/test_hardening_persian.py` | 11 | yeh / kaf / alef maksura, ZWNJ rules, id digits, empty text, Arabic-Indic digits in fa vs en |
| Files and metadata | `hardening/test_hardening_files.py` | 14 | SHA-256 of a file, document id and language from a file name, repo-root search, bilingual pair lookup |
| RAG config | `hardening/test_hardening_configs.py` | 6 | empty or non-mapping sections, a non-mapping file, an empty file, misspelt keys |
| Coverage domain | `quality/test_quality_coverage.py` | 20 | percentages, context mapping, impossible counts, totals per context, least covered modules, gate |
| Coverage / inventory readers | `quality/test_quality_reports.py` | 10 | `coverage json` parsing and filtering, bad entries, missing file, static test count |
| Release checklist | `quality/test_quality_checklist.py` | 13 | deliverable rules, problems, phase status, YAML shape, the shipped checklist |
| Release / readiness | `quality/test_quality_release.py` | 13 | quality config, Phase 14 choice re-check, readiness, the Phase 15 script (2 slow tests) |
| Phase 14 carry-overs | `tuning/test_tuning_carryover.py` | 22 | fact pre-check, pre-checked judge, invented-id guard, new defaults |
| **Total** | | **150** | |

Expected pytest total: 1493 (Phase 14) + 150 = **1643 passed**.

## 4. Defects found and fixed

| Id | Module | Defect | Fix |
|---|---|---|---|
| D15-1 | `shared_kernel/numerals.py` `parse_decimal` | `Decimal()` also accepts `NaN`, `Infinity` and exponent forms such as `1e5`, so a text value could turn into a non-number or a much larger number | the normalized text must be a plain signed decimal; anything else raises `ValueError` |
| D15-2 | `rag/infrastructure/config.py` | `data or {}` made an empty list or empty string section silently mean "defaults"; a file that was a list raised a raw `TypeError` | only a missing / `null` section means defaults; any other non-mapping raises `InvariantError`; the file itself must be a mapping |
| D15-3 | `shared_kernel/language.py` `LanguageCode.parse` | a `None` or number raised `AttributeError` | raises `InvariantError("unsupported language")` like any other bad value |
| D15-4 | `tuning` (Phase 14 finding) | the strict LLM judge accepted 2 of 3 answers that dropped a reference fact | `strict_precheck`: a deterministic fact / id pre-check in front of the strict judge |
| D15-5 | `tuning` (Phase 14 finding) | `listed_retry` asks again only for missing ids, so a text with an invented id was kept and then rejected (1 invented id in the live run) | `listed_guarded`: one more request when an id was invented; the text with fewer invented ids wins; a text that still invents one is rejected |

Found but **not changed** (changing them would alter ingestion output that earlier phases
measured):

* `normalize_zwnj` inserts a half-space after a word-initial `می` even when it is part of the
  word (`میلیون`, `میز`). Fact matching removes ZWNJ, so retrieval and judging are not affected;
  only the stored text shows the extra half-space.
* `document_id_from_name` reads only three digits, so a file named after a contract id
  (`AR-CNT-1402-118…`) gets the id `AR-CNT-140`. No corpus file is named that way.

## 5. Phase 14 carry-overs

* **New defaults.** `config/eval.yaml` now selects `retrieval=baseline` and
  `qa_prompt=qa.answer`, with the measured reasons (Phase 14 run of 3 Azar 1405: all retrieval
  variants 62/62 context facts, wide equal to baseline live; qa.answer 62/62 facts vs 60/62).
  `judge_prompt=strict_precheck`, `ai_ids=listed_guarded`. The Phase 14 live step of the same
  setup run was expected to agree on all four; Phase 15 prints one `live_confirm` line per kind.
  Measured: 3 of 4 agreed, `ai_ids` did not (section 6).
* **Fact pre-check.** For an answer, every reference fact group must appear (same word
  normalization as the rule judge). For a summary, every required id must appear. Refusal cases
  are not pre-checked. On the 42 calibration cases the prediction was 9–11 flagged, 0 false flags,
  `drop_fact` 3/3, `wrong_number` 2/2, `refuse_answerable` 2/2, `fake_label` 0/3 (left to the
  LLM judge), `wrong_language` 0–2/4 (measured: 11 flagged, 0 false flags, wrong_language 2/4). A flagged case is rejected without a model call.
* **Invented-id guard.** Offline control with a fake model that invents `AR-ISS-999` once:
  `listed_retry` accepts 0/2, `listed_guarded` 2/2 with 0 invented ids.

## 6. Results on the target system

Run of 20261123T215647Z (UTC), about 01:26 Tehran time on 3 Azar 1405, Fedora Linux,
Python 3.15.2, Ollama 0.40.17. Status **PASS**, 11/11 checks ok.

| Item | Value |
|---|---|
| pytest | **1643 passed** (0 failed, 0 errors, 0 skipped) in 57.70 s, as predicted (1493 + 150) |
| Line coverage | **96.3 %** (13 743 / 14 275 statements, 289 modules) |
| Branch coverage | **89.6 %** (3 523 / 3 930 branches) |
| Gate (>= 80 %) | ok, 16.3 points above the gate (the estimate was 85–90 %) |
| Tool | coverage.py 7.17.5 |
| Test inventory | 22 folders, 153 files, 1255 test functions; Phase 15: hardening 46, quality 34, carryover 22 functions |
| Earlier phase checks | all 0 (`ingest … rfp`, `eval`) |

### Coverage per context

| Context | Line | Context | Line | Context | Line |
|---|---|---|---|---|---|
| executors | 95.8 % | judging | 96.9 % | quality | 98.3 % |
| hierarchy | 91.5 % | knowledge | 92.6 % | rag | 97.5 % |
| ike | 96.7 % | models | 86.5 % | rag_core (top level) | 100.0 % |
| ingestion | 90.4 % | prioritization | 98.2 % | research_gaps | 100.0 % |
| issues | 96.1 % | processing | 100.0 % | rfp | 97.9 % |
| projects | 96.8 % | proposals | 98.3 % | shared_kernel | 99.0 % |
| qa | 98.7 % | transfer | 96.6 % | tuning | 98.7 % |

Least covered modules (>= 20 statements): `ingestion/infrastructure/parser_doc.py` 76.2 %,
`ingestion/infrastructure/parser_pdf.py` 78.8 %, `executors/infrastructure/memory.py` 80.0 %,
`knowledge/infrastructure/memory.py` 81.0 %, `rag/infrastructure/memory.py` 81.8 %,
`knowledge/domain/services.py` 82.7 %, `models/infrastructure/memory.py` 83.3 %,
`ingestion/application/pipeline.py` 84.1 %, `ingestion/domain/model.py` 84.2 %,
`transfer/domain/model.py` 86.3 %. As expected, the lowest are the parsers that call external
tools (`.doc`, `.pdf`) and the in-memory test repositories, whose unused query methods are
not exercised. No context is below 85 %.

### Carry-overs measured

| Item | Result |
|---|---|
| Pre-check offline | 42 cases, 39 pre-checked, **11 flagged**, 0 false flags; by mutation drop_fact 3/3, wrong_number 2/2, refuse_answerable 2/2, wrong_language 2/4, fake_label 0/3; 11 of 20 gold rejects caught before the model; the fake judge was called 31 times |
| Invented-id guard offline | listed_retry accepted 0/2 (2 invented), listed_guarded 2/2 (0 invented) |
| `strict_precheck` live | **38/42, kappa 0.809**, leniency 0.100, 2 false accepts, 2 false rejects; drop_fact **3/3** (strict alone: 36/42, kappa 0.712, drop_fact 1/3); 11 cases decided by the pre-check, 31 model calls, 1.00 s per call |
| Live confirmation | retrieval=baseline agrees, qa_prompt=qa.answer agrees, judge_prompt=strict_precheck agrees, **ai_ids disagrees** (measured baseline) |
| Readiness | ready=yes, live_confirmed 3/4, advisory `disagrees:ai_ids=baseline` |

`qa_prompt`: in this run both prompts found 60/62 facts (status 31/32, grounded 32/32);
`qa.answer` stays because the selection rule keeps the baseline when the gain is below 0.02.
`qa.answer_complete` gave all 4 Q06 causes in both languages (qa.answer 4/4 fa, 3/4 en).

### The ai_ids disagreement

| Variant | Named ids | All ids | Accepted | Invented | Retries | Avg s |
|---|---|---|---|---|---|---|
| baseline | 11/18 | 1/4 | **2/4** | 0 | 0 | 5.13 |
| listed | 9/18 | 1/4 | 1/4 | 1 | 0 | 5.93 |
| listed_retry | 15/18 | 3/4 | 2/4 | 1 | 3 | 9.49 |
| listed_guarded | 9/18 | 1/4 | 1/4 | **0** | 3 | 9.02 |

`listed_guarded` did what it was built for, no invented ids. But its guard retry names fewer
ids than the missing-id retry of `listed_retry`, so it named only 9 of 18 required ids, and
only 1 of the 4 texts was accepted. The plain baseline prompt was accepted 2 of 4 times, so the
selection rule (accept rate first) measured `baseline`. The sample is very small (4 texts, one
accepted text is 25 points), so this is not a stable ranking. As agreed, the shipped config and
code were **not** changed after the run: `ai_ids` stays `listed_guarded` in the tested commit.

**Open for Phase 16:** decide `ai_ids`. Most likely switch to `baseline` (better acceptance
here), or keep `listed_guarded` for its safety (no invented ids). A combined variant (the
missing-id retry of `listed_retry` plus the invented-id rejection) and a larger id sample are
the obvious next measurements.
