# Phase 10 — LLM-as-judge and quality control: scoring framework

Kit version 0.10.0. Phase 10 adds a judge that scores the key outputs of the system, the Phase 8 node-scoped answers and the Phase 9 issue summaries, against a 20-point rubric and accepts an output only at **18/20 or more with every criterion at or above its minimum** (the initial acceptance bar of the project plan).

There are no new dependencies. Unit tests use fakes and never need Ollama, the GPU or the internet. The live judge is `qwen3:8b` on the local Ollama (think off, temperature 0, JSON format).

Target system: Ubuntu 24.04.5 LTS, Python 3.12.3, Ollama 0.40.2, project at `~/Desktop/RAG`.

## 1. Where things live

Issue #10 lists `src/judge/ (rubric, parser, threshold)`. As in earlier phases, the code extends the existing Phase 3 bounded context `rag_core.judging` rather than adding a parallel package:

| Issue #10 output | Code |
|---|---|
| rubric | `judging/domain/rubric.py` (`Criterion`, `Rubric`, `OutputKind`, `default_rubric`), file `config/prompts/judge/rubric.yaml`, loader `judging/infrastructure/prompt_yaml.py` |
| judging prompts | `config/prompts/judge/qa.yaml`, `config/prompts/judge/summary.yaml`, model `judging/domain/prompts.py` (`JudgePromptSet`) |
| score parser | `judging/domain/parser.py` (`JudgeOutputParser`, `ParsedJudgement`) |
| thresholds | `judging/domain/threshold.py` (`AcceptancePolicy`, `Decision`, `PolicyOutcome`), built on the Phase 3 `JudgeThreshold(18, 20)` |
| judges | `judging/domain/rule_judge.py` (`RuleBasedJudge`), `judging/application/services.py` (`LlmJudge`, `judge_all`) |
| quality control | `judging/domain/negative.py` (negative controls), `judging/domain/metrics.py`, `data/judge/calibration-set.json` |
| ACLs | `judging/infrastructure/qa_acl.py` (Phase 8 answers), `judging/infrastructure/ike_acl.py` (Phase 9 summaries) |
| tests | `tests/unit/judge/` (score parsing, thresholds, rubric, judges, negative controls, configs, script) |
| run | `scripts/run_judge_check.py`, called last by `scripts/setup_and_test.sh` |

Ports: `JudgeModelPort.generate(system, user) -> LlmResult` (implemented by the Phase 8 `OllamaChatModel`; a fake in tests) and `CaseJudge.judge(case) -> JudgeResult` (the rule judge and the LLM judge). The domain never calls Ollama.

## 2. Rubric `judge.rubric@1.0.0`

| Criterion | Key | Max | Min | qa_answer | qa_refusal | ike_summary |
|---|---|---|---|---|---|---|
| Grounding | `grounding` | 5 | 4 | every number, name and id is in the SOURCES | no factual claim beyond the question | everything is in the FACTS |
| Correctness | `correctness` | 5 | 4 | the right facts for this question | the right behaviour (decline / escalate) | each sub-issue with its own owner and lead |
| Citation | `citation` | 4 | 3 | bracket labels point at given SOURCES blocks | no invented labels | every sub-issue id mentioned |
| Completeness | `completeness` | 3 | 2 | all key facts | escalation target, or what is missing | knowledge gaps and dependencies |
| Language and clarity | `clarity` | 3 | 2 | question language, short, no leftovers | same | same, plain text |

Total 20. The guidance text per output kind is in `rubric.yaml` and is shown to the LLM judge as its scoring scale. Anchors (for example "5 = fully supported, 3 = one small unsupported detail, 0-2 = an invented number") keep the judge's scale fixed. Each criterion has aliases that the parser accepts (`groundedness`, `faithfulness` → `grounding`; `accuracy` → `correctness`; `citations`, `traceability` → `citation`; `coverage` → `completeness`; `language`, `fluency` → `clarity`).

### Spec §16.1 sample rubric → kit criteria (traceability only)

The project plan sample rubric lists **7** criteria. The kit keeps its own **5-criterion** weights (`5/5/4/3/3`) and minima; the table below is for **traceability** between the sample wording and the kit keys. It does not change scoring.

| Spec §16.1 sample criterion (points) | Maps to kit criterion |
|---|---|
| Faithfulness to source (5) | `grounding` |
| Completeness vs user request (4) | `completeness` |
| Detail level fit for target layer (3) | `clarity` + `completeness` |
| Handling uncertainty and gaps (3) | `correctness` |
| Clarity and professional structure (2) | `clarity` |
| Source traceability (2) | `citation` |
| No unsupported claims (1) | `grounding` |

## 3. Thresholds

`AcceptancePolicy.decide(scores)`:

* `total < 18` → reject with reason `total X<18`;
* any criterion below its minimum → reject with `key s<min`. Example: 3+5+4+3+3 = 18 is rejected because grounding 3 < 4;
* a missing criterion counts as 0 and is reported as `missing:key`;
* optional hard failures reject with `hard:<reason>`;
* an unreadable judge reply is an `error` decision. It is never an acceptance and never a silent 0 (Phase 3 rule).

The minimums alone add up to 15, so passing every minimum is not enough. A high total cannot hide a weak criterion either.

## 4. Score parser

The parser tries these in order and the first that yields at least one criterion wins:

1. `json`: the whole reply is a JSON object;
2. `json_extracted`: the first balanced `{...}` inside prose, code fences or `<think>` text. A reply cut off by `num_predict` is closed (open string, then open `[`/`{`);
3. `json_repaired`: trailing commas, single quotes, unquoted keys, `True/False/None`;
4. `key_value`: lines such as `Grounding: 4/5`, `**citation** = 3`, `clarity: 2 out of 3`.

Accepted shapes are `{"scores": {...}}`, `{"scores": {"grounding": {"score": 4}}}`, flat `{"grounding": 4}` and lists `[{"criterion": ..., "score": ...}]`. Persian digits are normalized. Floats are rounded half up. A fraction on another scale (`3/5` for a 4-point criterion) is rescaled. Out-of-range values are clamped and reported. A total written by the judge is ignored and recomputed, and a mismatch is reported as `total_mismatch`. Non-numeric values are reported and the criterion is listed as missing. No score at all raises `JudgeParseError`.

The fixtures in `data/judge/parser-cases.json` (17 cases: json 9, json_extracted 2, json_repaired 2, key_value 1, error 3) are run by the unit tests and by the check script.

## 5. Two judges

**Rule judge** (`RuleBasedJudge`, offline, deterministic):

* grounding: the Phase 8 `CitedFactValidator` (shared-kernel `FactValidator` port) costs 2 points per unsupported number or id;
* correctness and completeness: share of the reference key facts (`data/rag/sample-questions.json`). For refusals, the status and the escalation target. For summaries, each sub-issue must be named in the same segment as its lead executor (Persian or English name) and the knowledge-gap targets must appear;
* citation: each bracket label must match a given source block (document, section, language). An invented label costs 2 points, and most sentences without a label costs 1. For summaries it is the share of sub-issue ids;
* clarity: the language share of Arabic-script letters (labels and ids ignored), length, `<think>`/code fences, and tables in summaries.

It is blind to meaning. Two correct numbers in swapped places look fine to it (calibration case `CAL-N06`, tag `rule_blind_spot`).

**LLM judge** (`LlmJudge`): renders the prompt for the output kind and sends system + user to `qwen3:8b` with Ollama `format: json`, temperature 0, seed 42, `num_ctx` 8192, `num_predict` 512 and a 180 s timeout. It parses the reply and applies the same policy. An unreadable or incomplete reply is asked again once with `retry_note`. A model failure becomes an `error` result, and `judge_all` stops after more than 2 consecutive failures. One 8B model at 8k context fits a 12 GB GPU, and no embedding model is loaded.

## 6. Self-judging bias

The judge is the same model that wrote the answers and summaries, so it may favour its own wording and miss its own mistakes. Mitigations in this kit:

1. **Evidence, not memory:** the judge sees the same SOURCES / FACTS as the writer, plus the reference key facts and the expected behaviour (answer, decline, escalate to N-CEO). Rules 3-5 of the system prompt cap grounding, citation and clarity for invented content.
2. **A second, independent opinion:** the rule judge scores every key output. The summary shows the agreement between the two judges (with Cohen's kappa) and `combined_with_rule` (accepted by both). For a key output, "accepted by both" is the safe reading.
3. **Calibration:** 14 hand-labelled cases (8 accept, 6 reject, text taken from the corpus) measure agreement with gold labels. `CAL-N06` shows where rules fail and the LLM judge should succeed.
4. **Negative controls:** broken copies of good outputs (wrong number, fabricated citation `AR-ZZZ-999 §99`, off-topic answer, refusing an answerable question, answering an out-of-scope question, dropped sub-issues, rotated lead executors). A judge that accepts these is not discriminating, whatever its acceptance rate on real outputs.
5. **Repeatability:** temperature 0, fixed seed, think off and a JSON format, so the same input gives the same score.
6. **Not part of PASS:** the kit status depends on the offline checks only. Live judge numbers are reported for review, not used to pass the kit.

Remaining risk: a shared blind spot of writer and judge (for example a plausible but wrong Persian paraphrase) can still pass both. A different judge model, or a human review of a sample, is the next step if the live numbers look too generous.

## 7. Check script and summary block

`scripts/run_judge_check.py` (last step of `setup_and_test.sh`):

* **offline:** rubric and prompts (render once per kind), parser fixtures, rule judge on the calibration set, the Phase 9 template summaries of AR-ISS-024 (offline graph as in Phase 9), the Phase 8 live answers and Phase 9 live summaries from the newest `results/phase-08/rag-demo-*.json` and `results/phase-09/ike-check-*.json` if those runs had a live step, and negative controls;
* **live** (only with Ollama and `qwen3:8b`): the LLM judge on the key outputs, the calibration set and the negative controls of the key outputs, at most 60 judge calls;
* **checks for PASS:** `pytest`, `prior_steps` (ingest, dedup, hierarchy, issues, rag, ike), `rubric_valid`, `prompts_render`, `parser_cases`, `calibration_rule_agrees` (without the blind spot), `negative_controls_rejected` (offline negatives: calibration + templates), `ike_templates_accepted`, `records_built`.

Results go to `results/phase-10/judge-check-<UTC>.json`, which is not committed. Phase 8 answers are judged against the chunk text from the Phase 8 index (`.rag-index/phase-08.sqlite`), or against a corpus rebuild if the index is missing. Phase 9 summaries are judged against the fact lines the summary was written from, which `run_ike_check.py` now stores in its live result.

Summary lines: `rubric`, `prompts`, `parser_cases`, `calibration_rule`, `negative_controls_rule`, `ike_templates_rule`, `phase8_answers_rule`, `phase9_summaries_rule`, `key_outputs_rule`, `live`, and with Ollama also `live_judge`, `live_key_outputs` (with one line per key output: LLM total, decision, rule total), `live_calibration`, `live_negative_controls`, `live_criterion_means` and `live_timings`, then `checks` and `results_json`.

## 8. Reference run

Test system: Ubuntu 24.04.5 LTS, Python 3.12.3; project at `~/Desktop/RAG`. Ollama 0.40.2, judge `qwen3:8b` (think off, temperature 0, JSON format).

- Run: 2026-11-19 12:14:02 UTC (2026-11-19 15:44 Tehran time, Asia/Tehran).
- Result: `status: PASS`, 937 passed, 0 failed, 0 errors, 0 skipped; earlier steps ingest, dedup, hierarchy, issues, rag and ike all exited 0.
- Rubric: `judge.rubric@1.0.0`, out of 20, accept at 18 or more, minima grounding 4/5, correctness 4/5, citation 3/4, completeness 2/3, clarity 2/3.
- Parser cases: 17/17 ok (json 9, json_extracted 2, json_repaired 2, key_value 1, error 3).
- Rule judge on calibration: agree 13/14, positives accepted 8/8, negatives rejected 5/6, blind spot `CAL-N06:accept`, check 13/13.
- Rule judge on negative controls: offline 10/10 rejected; from live outputs 12/12 rejected.
- Rule judge on Phase 9 template summaries: Persian 20/20 accept, English 20/20 accept.
- Rule judge on Phase 8 answers (file `results/phase-08/rag-demo-20261119T121315Z.json`, sources from `.rag-index/phase-08.sqlite`): 10 answers, 9/10 accepted, mean total 19.7, rejected `P8-Q06` at 17.
- Rule judge on Phase 9 summaries (file `results/phase-09/ike-check-20261119T121350Z.json`): Persian 19/20 accept, English 20/20 accept.
- Rule judge on key outputs: 13/14 accepted, rate 0.929.
- Live step: `ok`. LLM judge: `qwen3:8b`, 42 cases, 42 calls, 0 retried, 0 errors, all parsed as `json`.
- Live key outputs: LLM accepted 14/14, rate 1.0, mean total 19.857, min total 18; agreement with the rule judge 13/14; Cohen's kappa 0.0 (degenerate: the LLM accepted every key output). Combined (both must accept): 13/14.
  - P8-Q01 to P8-Q05 and P8-Q07 to P8-Q10: LLM 20/20 accept, rule 20.
  - P8-Q06: LLM 20/20 accept, rule 17 reject.
  - P9-TEMPLATE-fa and P9-TEMPLATE-en: LLM 20/20 accept, rule 20.
  - P9-LLM-fa: LLM 18/20 accept, rule 19.
  - P9-LLM-en: LLM 20/20 accept, rule 20.
- Live calibration: agree 12/14, positives accepted 8/8, negatives rejected 4/6. Disagreements: `CAL-N03` accepted at 20 (right facts, wrong language; gold reject) and `CAL-N06` accepted at 20 (swapped numbers; the intended LLM catch of the rule-judge blind spot was missed).
- Live negative controls: 13/14 rejected, rate 0.929. Accepted negative: `P8-Q08~refuse_answerable` at 20.
- Live criterion means (all 42 live cases): grounding 3.619/5, correctness 3.69/5, citation 2.976/4, completeness 2.262/3, clarity 2.714/3.
- Live timings: judge average 2.279 s, p95 4.131 s, tokens average 1653+92, total 95.7 s. All checks ok.
- Results file: `results/phase-10/judge-check-20261119T121402Z.json`.

The main finding is that the LLM judge, which is the same model as the generator, was lenient. It scored almost every key output 20/20, accepted `P8-Q06` that the rule judge had rejected at 17, accepted calibration rejects `CAL-N03` and the blind-spot case `CAL-N06`, and accepted one `refuse_answerable` negative control. Kappa on the key outputs is 0.0 because the LLM accepted all of them, so it does not measure agreement. The safe verdict is therefore the combined rule: both judges must accept, which is 13/14. Later evaluation phases (14 and 15) should use a stricter judge prompt with a reference-fact checklist, a different judge model, and a larger calibration set.

## 9. Limits and open points

* The rule judge checks numbers and ids, not person names in answers and not meaning. The reference run confirmed the `CAL-N06` blind spot (swapped numbers accepted).
* The LLM judge shares the writer's model (§6). The reference run confirmed the leniency risk: near-all 20/20 scores, acceptance of `P8-Q06`, of `CAL-N03` and `CAL-N06`, and of one `refuse_answerable` negative. Kappa on key outputs was 0.0 because the LLM accepted every item. The combined verdict (both must accept) is the reading to use.
* Key facts come only from the ten Phase 8 sample questions. New questions need reference facts for a strict correctness score.
* The 18/20 bar is initial. A stricter judge prompt with a reference-fact checklist, a different judge model, and a larger calibration set belong in phases 14 and 15.
