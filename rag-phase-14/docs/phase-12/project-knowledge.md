# Phase 12 — Project, research, achievement and gap tracking

Kit version 0.12.0 (GitHub issue #12). Phase 12 adds a **project tracking register** for the reporting cycle `1403-Q2` (cutoff 1403-06-31), a set of **research-gap rules**, and a **weighted, explainable prioritization** that picks the key issues for the chief executive and writes a short key-issue brief in Persian and English. The brief is judged with the Phase 10 rubric (accept at 18/20). An optional live step asks `qwen3:8b` (think off, JSON) for advice; the advice never changes the ranking.

There are no new dependencies. Unit tests never need Ollama, the GPU or the internet.

Target system: Fedora Linux, Python 3.15.2, LibreOffice 26.8.3.1, pdftotext 26.08.0, Intel Core i5-12400F, 16 GB RAM, NVIDIA RTX 3060 12 GB, project at `~/Desktop/RAG`.

## 1. Where things live

Issue #12 names `src/projects/`, `src/research_gaps/` and `src/prioritization/`. As in earlier phases they are bounded contexts inside the `rag_core` package.

| Issue #12 output | Code |
|---|---|
| project / achievement / challenge / research / unsolved-issue records | `projects/domain/model.py` (`Project`, `TrackRecord`, `ScorecardDimension`, `ProjectRegistry`) |
| register validation | `projects/domain/validation.py` (`RegistryValidator`, `IssueFacts`, `health`) |
| evidence grounding | `projects/domain/evidence.py` (`ground_project`, `ground_record`, `ground_registry`) |
| tracking views | `projects/application/services.py` (`ProjectTrackingService`: overview, matrix, open research, remaining value) |
| storage and settings | `projects/infrastructure/registry_json.py`, `csv_export.py`, `config.py` |
| ACLs to other contexts | `projects/infrastructure/issues_acl.py` (Phase 7 issues), `corpus_acl.py` (Phase 5 active versions) |
| research-gap rules | `research_gaps/domain/model.py`, `research_gaps/domain/rules.py` (`GapRuleBook`), `research_gaps/application/services.py` (`GapReport`, `GapService`), `research_gaps/infrastructure/inputs_acl.py` |
| prioritization | `prioritization/domain/model.py` (`Weights`, `Caps`, `IssueSignal`, `ScoredIssue`), `scoring.py` (`PriorityScorer`, `legacy_order`, `sensitivity`), `unblocking.py` (`next_actions`) |
| key-issue brief | `prioritization/domain/brief.py` (`build_brief`), `prioritization/infrastructure/judging_acl.py` (brief → Phase 10 judge case, negative copies) |
| AI advice | `prioritization/domain/advice.py` (`advice_prompt`, `parse_advice`, `check_advice`) |
| settings | `config/projects.yaml` |
| run + summary | `scripts/run_project_check.py` (called last by `scripts/setup_and_test.sh`) |
| tests | `tests/unit/projects/`, `tests/unit/research_gaps/`, `tests/unit/prioritization/`; helpers `tests/fixtures/projects/samples.py` |

The dependency direction stays hexagonal: domain modules import only the shared kernel and their own context; anything that reads another context's aggregates (issues, hierarchy, corpus, IKE digest, judges) is an ACL in `infrastructure/`.

## 2. The register

`data/projects/project-registry.json` (schema 1) holds:

* **3 projects** — `PRJ-AZP-118` Azarpakhsh warehouse system (contract AR-CNT-1402-118, 2,180M toman, 62%, 1,240M remaining, primary issue AR-ISS-024, status `at_risk`), `PRJ-RHS-PORTAL` Rahavard Sanat service portal (78%, 410M remaining, AR-ISS-033), `PRJ-DSP-VISITOR` Dashtpakhsh visitor app (45%, 225M remaining, AR-ISS-031);
* **15 records** — 5 achievements (3 recorded, 2 conditional), 4 challenges, 2 open research questions and 4 unsolved issues;
* **5 scorecard dimensions** — referral coverage and management transfer recorded, capacity control and reproducibility conditional, repair retrieval quality open (linked to `RES-RETRIEVAL-EVAL`).

Record and dimension ids contain no digits on purpose, so the fact checker never reads a number out of an id. Every statement uses only numbers and identifiers found in its cited documents (AR-TRN-026 and AR-FIN-008).

Invariants enforced by the model: progress in 0..100, non-negative amounts, remaining ≤ contract, the primary issue is one of the project's issues, a completed project is at 100%. Research records may never claim a validated result.

### Validation (`RegistryValidator`)

Problems are reported as `code:ref`. Checks, in order: duplicate ids; per project unknown nodes / documents / issues, missing evidence and status inconsistent with issue health; per record unknown nodes / documents / issues / project, missing evidence, lessons (achievements, challenges) without conditions, recorded achievement still open, research claiming a result or with an incomplete plan (people, risks, evidence needed), unsolved issue without an issue or whose issues are all closed; scorecard unknown documents or research.

Health: `at_risk` when an open issue has risk ≥ 7 or blocked sub-issues; `watch` when an issue is open; otherwise `on_track`.

### Evidence grounding

Each project's numbers (progress, remaining, contract) must appear in the active text of its evidence documents; each record statement is checked in both languages with the shared `CitedFactValidator`.

## 3. Research-gap rules

| code | name | fires when | default severity |
|---|---|---|---|
| RG | research_open | research record open or conditional (one level up if linked to an open issue) | medium |
| KL | knowledge_lack | active sub-issue has Phase 9 knowledge lacks (high if blocked) | medium |
| EX | missing_executor | active sub-issue has no IKE lead and no executor | high |
| DEP | blocked_dependency | blocked sub-issue waits for an unresolved sibling | high |
| CH | unlinked_challenge | challenge not linked to a registered issue | medium |
| SC | scorecard_open | dimension open (conditional: one level down) | medium |
| ST | stale_unsolved | unsolved-issue record whose linked issues are all closed | low |
| EV | unevidenced_record | record without evidence | high |

Gap ids are `RULE:subject` (e.g. `DEP:AR-ISS-024/WIN`); gaps are sorted by severity, rule order and subject. Rules can be switched off or re-graded in `config/projects.yaml`.

Expected on the shipped data: RG 2, DEP 2 (`AR-ISS-024/WIN`, `AR-ISS-024/LEG`), CH 3, SC 3, plus one KL gap per AR-ISS-024 sub-issue with knowledge lacks in the Phase 9 digest.

## 4. Prioritization

Each open, non-duplicate issue becomes an `IssueSignal`; nine factors are normalized to [0, 1] and weighted (weights sum to 1, so a score is 0..100):

| factor | value | weight |
|---|---|---|
| priority | P1 1.0, P2 0.75, P3 0.5, P4 0.25 | 0.15 |
| severity | critical 1.0, high 0.75, medium 0.5, low 0.25 | 0.10 |
| urgency | urgency / 10 | 0.15 |
| risk | risk / 10 | 0.15 |
| dependents | dependents / 4 | 0.10 |
| exposure | money at stake / 1000M toman (decision amount, or remaining value for a project's primary issue) | 0.10 |
| blocked | blocked sub-issues / sub-issues | 0.10 |
| gaps | open gaps on the issue / 5 | 0.10 |
| spread | affected nodes / 6 | 0.05 |

Ties: higher risk, then higher urgency, then issue id. Key issues: the top 3 with score ≥ 25. Excluded: closed issues and duplicates (`AR-ISS-036` is a duplicate of `AR-ISS-024`).

Expected scores: AR-ISS-024 72.75 + 2 × (its gaps, capped at 5) — 80.75 with 4 gaps; AR-ISS-031 33.92; AR-ISS-035 30.17; AR-ISS-032 28.33; AR-ISS-033 17.18. Key issues AR-ISS-024, AR-ISS-031, AR-ISS-035.

* **Legacy comparison** — the Phase 7 order (`3·urgency + 2·risk + dependents`) is AR-ISS-024, AR-ISS-031, AR-ISS-032, AR-ISS-035, AR-ISS-033: same top issue, top-3 overlap 2/3.
* **Sensitivity** — each weight × 0.8 and × 1.2 with renormalization (18 runs); expected 18/18 for the top issue and the key set.
* **Next action** — inside a key issue, the open, not-blocked sub-issue that unblocks the most others (directly or through a chain): `AR-ISS-024/HW` unblocks `AR-ISS-024/LEG` and `AR-ISS-024/WIN`.

## 5. Key-issue brief and AI advice

`build_brief` writes fact lines and a template from the same values: cycle and cutoff, each key issue with rank, score, status, top three factors, progress and money at stake, up to 6 gaps on key issues, the next action and up to 2 research gaps. The brief is judged as an `ike_summary` case: FACTS is the only source, every key issue id must appear and the gap subjects should be named. Negative copies (invented number, invented id, key lines removed) must be rejected.

Live step (optional): `qwen3:8b`, think off, JSON format, `num_predict` 768. The reply (`brief`, `order`) is parsed, every number and id must be in the facts, every id in `order` must be a ranked issue, and the rule judge (plus the LLM judge when enabled) must accept. The result is stored in the results JSON as advice only.

## 6. Outputs

* `exports/project-tracking/1403-Q2/{projects,records,gaps,priorities}.csv` (UTF-8 with BOM, lists joined with `;`), read back after writing;
* `results/phase-12/project-check-<UTC>.json` with every check, the ranking, gaps, briefs, negative controls and the live result.

## 7. Results on my system

Run on 2 Azar 1405 at about 22:27 Tehran time (UTC+3:30) on Fedora Linux, Python 3.15.2, i5-12400F, 16 GB RAM, RTX 3060 12 GB, Ollama with `qwen3:8b`. Status **PASS**, all 14 checks ok.

```text
======== PHASE 12 SUMMARY ========
status: PASS
kit: rag-core 0.12.0 (phase 12 projects, research gaps, prioritization)
python: 3.15.2
pytest_exit: 0
pytest_passed: 1207
pytest_failed: 0
pytest_errors: 0
pytest_skipped: 0
prior_steps: ingest=0 dedup=0 hierarchy=0 issues=0 rag=0 ike=0 judge=0 transfer=0
cycle: 1403-Q2 cutoff=1403-06-31 case=AR-ISS-024 ike_items=4 executors=15
registry: projects=3 records=15 (research=2 achievement=5 challenge=4 unsolved_issue=4) scorecard=5 problems=0
  PRJ-AZP-118: progress=62% remaining=1240 contract=2180 owner=N-CEO status=at_risk health=at_risk issues=4 open=3 blocked_sub=2 records=achievement:1,challenge:1,unsolved_issue:3
  PRJ-RHS-PORTAL: progress=78% remaining=410 contract=- owner=N-SW-WEB status=active health=watch issues=2 open=1 blocked_sub=0 records=achievement:1
  PRJ-DSP-VISITOR: progress=45% remaining=225 contract=- owner=N-SW-MOB status=active health=watch issues=1 open=1 blocked_sub=0 records=achievement:1,unsolved_issue:1
evidence: projects fa=3/3 en=3/3 records fa=15/15 en=15/15
gaps: total=14 by_rule=RG:2,KL:4,DEP:2,CH:3,SC:3 by_severity=high:4,medium:8,low:2
  KL:AR-ISS-024/LEG high issue=AR-ISS-024 lacks=1; status=blocked
  KL:AR-ISS-024/WIN high issue=AR-ISS-024 lacks=1; status=blocked
  DEP:AR-ISS-024/LEG high issue=AR-ISS-024 waits_for=AR-ISS-024/HW
  DEP:AR-ISS-024/WIN high issue=AR-ISS-024 waits_for=AR-ISS-024/HW
  RG:RES-PHOTO-TRIAGE medium state=open; people=2
  RG:RES-RETRIEVAL-EVAL medium state=open; people=2
  KL:AR-ISS-024/HW medium issue=AR-ISS-024 lacks=2; status=in_progress
  KL:AR-ISS-024/WEB medium issue=AR-ISS-024 lacks=1; status=in_progress
  CH:CHL-KEY-CAPACITY medium no registered issue tracks this challenge
  CH:CHL-LOST-CONDITIONS medium no registered issue tracks this challenge
  CH:CHL-REPAIR-NOTES medium no registered issue tracks this challenge
  SC:SC-RRQ medium state=open; research=RES-RETRIEVAL-EVAL
  SC:SC-CAP low state=conditional
  SC:SC-REP low state=conditional
priorities: ranked=5 excluded=2 (AR-ISS-034:closed,AR-ISS-036:duplicate_of:AR-ISS-024) key=AR-ISS-024,AR-ISS-031,AR-ISS-035 (top 3, score >= 25)
  1. AR-ISS-024 score=82.75 KEY top=urgency 12, risk 12, priority 11.25
  2. AR-ISS-031 score=33.92 KEY top=priority 7.5, urgency 7.5, risk 7.5
  3. AR-ISS-035 score=30.17 KEY top=priority 7.5, urgency 7.5, risk 6
  4. AR-ISS-032 score=28.33 top=risk 9, priority 7.5, urgency 6
  5. AR-ISS-033 score=17.18 top=money at stake 4.1, priority 3.75, urgency 3
sensitivity: perturbations=18 top1_stable=18/18 key_set_stable=18/18
legacy: phase7_order=AR-ISS-024,AR-ISS-031,AR-ISS-032,AR-ISS-035,AR-ISS-033 same_top1=True top3_overlap=2/3
next_action: AR-ISS-024 -> AR-ISS-024/HW unblocks=2 (AR-ISS-024/LEG,AR-ISS-024/WIN)
brief fa: key=3 gaps=6 words=175 chars=1282 rule=20 accepted
brief en: key=3 gaps=6 words=163 chars=1359 rule=20 accepted
negative_controls: registry rejected=9/9 brief rejected=6/6 by_kind=wrong_number:2/2,fabricated_id:2/2,drop_items:2/2
csv: files=4 dir=exports/project-tracking/1403-Q2 round_trip_problems=0
live: ok
live_brief: model=qwen3:8b think=off format=json generated=2 parse_errors=0 grounded=2/2 invented_ids=0 same_top=2/2 accepted=0/2
live_judge: ai rule=0/2 llm=1/2 combined=0/2 templates llm=2/2
  brief fa: rejected order=AR-ISS-024,AR-ISS-031,AR-ISS-035 mentioned=3 rule=18 llm=16
  brief en: rejected order=AR-ISS-024,AR-ISS-031,AR-ISS-035 mentioned=3 rule=18 llm=18
live_timings: brief_avg_s=4.039 judge_avg_s=2.029 tokens_avg=1006+202 total_s=16.2
checks: pytest=ok prior_steps=ok registry_loaded=ok records_built=ok registry_valid=ok evidence_grounded=ok research_gaps_tracked=ok gaps_detected=ok ranking_complete=ok key_issues_selected=ok ranking_stable=ok brief_accepted=ok negative_controls_rejected=ok csv_round_trip=ok
results_json: /home/mdhdl/Desktop/RAG/results/phase-12/project-check-20261123T185733Z.json
======== END PHASE 12 SUMMARY ========
```

| item | expected | actual |
|---|---|---|
| tests | 1061 + 146 = 1207 | 1207 passed, 0 failed, 0 errors, 0 skipped |
| register problems | 0 | 0 |
| evidence | 3/3 and 15/15 per language | 3/3 and 15/15 in fa and en |
| gaps | 10 + KL | 14 (RG 2, KL 4, DEP 2, CH 3, SC 3; high 4, medium 8, low 2) |
| key issues | AR-ISS-024, AR-ISS-031, AR-ISS-035 | same |
| AR-ISS-024 score | 72.75 + 2 × min(gaps, 5) | 82.75 (6 gaps, capped at 5) |
| other scores | 33.92, 30.17, 28.33, 17.18 | same |
| sensitivity | 18/18, 18/18 | 18/18, 18/18 |
| legacy comparison | same top, 2/3 overlap | same top, 2/3 overlap |
| next action | AR-ISS-024/HW | AR-ISS-024/HW unblocks LEG and WIN |
| briefs | accepted (fa, en) | rule 20 and 20, accepted; LLM judge 2/2 |
| negative controls | 9/9 register, 6/6 brief | 9/9, 6/6 |
| CSV | 4 files, 0 problems | 4 files, 0 problems |
| live advice | optional | 2 generated, 0 parse errors, 2/2 grounded, 0 invented ids, same top 2/2, accepted 0/2 |

Notes:

* The Phase 9 digest reports knowledge lacks on all four AR-ISS-024 sub-issues, so four KL gaps were added (WIN and LEG high because they are blocked). AR-ISS-024 therefore has 6 gaps and its gap factor is at the cap.
* The AI briefs invented nothing and proposed the same order as the deterministic ranking. The rule judge gave each 18/20 but did not accept, so at least one criterion was below its minimum (most likely completeness: not every gap subject named). The LLM judge gave fa 16 and en 18 (accepted). Under the combined rule (both judges must accept) the result is 0/2. The advice has no effect on the ranking or the exports.
* Live timings: brief about 4.0 s, judge about 2.0 s, about 1006 prompt + 202 completion tokens per brief, 16.2 s in total.
* Results file: `results/phase-12/project-check-20261123T185733Z.json`.

## 8. Limits

* Weights are a design choice; the sensitivity check shows ±20% does not change the result, not that the weights are right.
* Money at stake uses the remaining contract value only for each project's primary issue.
* Knowledge lacks come from the Phase 9 digest of AR-ISS-024 only.
* Research records are questions and plans; none is reported as a validated result.
* The AI advice never changes the ranking, the register or the CSV files.
