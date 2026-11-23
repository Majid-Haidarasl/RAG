# Phase 13 — RFP generation and proposal management

Kit version 0.13.0 (GitHub issue #13). Phase 13 turns the Phase 12 key issues and knowledge gaps into a **request for proposal (RFP)**, registers the received **proposals**, scores them against the RFP criteria with **transparent weights**, checks the recorded decision, writes **automated feedback** per bidder and **links the outcome back to node knowledge**. Generation is template-first: every number and identifier in the RFP and the feedback comes from reviewed data that is grounded in the corpus. An optional live step asks `qwen3:8b` (think off, JSON) for an RFP summary and bidder feedback; it is advisory only and is judged by the Phase 10 rule and LLM judges.

There are no new dependencies. Unit tests never need Ollama, the GPU or the internet. The code runs on Python 3.12 to 3.15.

Target system: Fedora Linux, Python 3.15.2, LibreOffice 26.8.3.1, pdftotext 26.08.0, Ollama 0.40.17, Intel Core i5-12400F, 16 GB RAM, NVIDIA RTX 3060 12 GB, project at `~/Desktop/RAG`.

## 1. Where things live

Issue #13 names an `rfp` generator and a `proposals` registry with evaluation and feedback. They are bounded contexts inside the `rag_core` package.

| Issue #13 output | Code |
|---|---|
| RFP blueprint (requirements, criteria, knowledge links) | `rfp/domain/blueprint.py` (`Requirement`, `Criterion`, `KnowledgeLink`, `Blueprint`, `Section`) |
| blueprint validation | `rfp/domain/validation.py` (`BlueprintValidator`) |
| blueprint grounding | `rfp/domain/evidence.py` (`ground_statement`, `ground_blueprint`) |
| candidate selection + RFP text | `rfp/domain/generator.py` (`select_candidates`, `relevant_gaps`, `build_rfp`) |
| AI advice (summary / feedback) | `rfp/domain/advice.py` (`parse_reply`, `check_reply`, `AiReply`) |
| use case | `rfp/application/services.py` (`RfpService`, `RfpRun`) |
| storage, settings, prompts | `rfp/infrastructure/blueprint_json.py`, `config.py`, `prompts_yaml.py` |
| ACLs | `rfp/infrastructure/inputs_acl.py` (Phase 7 issues, Phase 12 ranking and gaps, Phase 9 executors), `judging_acl.py` (Phase 10 judge cases) |
| proposal registry | `proposals/domain/model.py` (`ProposalRecord`, `Decision`, `ProposalRegistry`), `proposals/infrastructure/registry_json.py` |
| registry validation and grounding | `proposals/domain/validation.py` (`ProposalValidator`), `proposals/domain/evidence.py` (`ground_registry`) |
| evaluation rubric | `proposals/domain/evaluation.py` (`evaluate`, `Evaluation`, `ProposalScore`, `ScoreLine`) |
| automated feedback | `proposals/domain/feedback.py` (`build_feedback`) |
| links to node knowledge | `proposals/domain/knowledge.py` (`link_knowledge`) |
| use case + CSV | `proposals/application/services.py` (`ProposalService`, `ProposalAudit`), `proposals/infrastructure/csv_export.py` |
| settings and prompts | `config/rfp.yaml`, `config/prompts/rfp/sections.yaml`, `rfp_summary.yaml`, `feedback.yaml` |
| data | `data/rfp/rfp-blueprints.json`, `data/proposals/proposal-registry.json` |
| run + summary | `scripts/run_rfp_check.py` (called last by `scripts/setup_and_test.sh`) |
| tests | `tests/unit/rfp/test_rfp_*.py` (marker `rfp_gen`), `tests/unit/proposals/` (marker `proposals`); helpers `tests/fixtures/rfp/samples.py` |

The Phase 1 `rfp/domain/model.py` (`compute_weighted_score`, `CriterionWeight`) is reused for the weighted score. Its AR-RFP-025 constants now hold the recorded subscores of both proposals (A 82 / 74, B 68 / 86).

## 2. Data

### 2.1 Blueprint `BP-WEB-REPORTING`

One reviewed blueprint for RFP **AR-RFP-1403-07** "Warehouse web reporting module (Azarpakhsh)", owner node `N-SW`, serving issues `AR-ISS-024` (sub-issue `AR-ISS-024/WEB`) and `AR-ISS-035`, reference document `AR-RFP-025`.

| Requirement | Section | Kind | Answered in |
|---|---|---|---|
| REQ-NEED | need | mandatory | problem_understanding |
| REQ-SCOPE | scope | mandatory | work_plan |
| REQ-DELIVERABLES | deliverables | mandatory | work_plan |
| REQ-EXCLUSIONS | exclusions | mandatory | work_plan |
| REQ-ARCHITECTURE | architecture | recommended (also AR-SW-016) | architecture |
| REQ-SECURITY | security | recommended | architecture |
| REQ-TESTING | testing | recommended | test_plan |
| REQ-RESPONSE | response_format | mandatory | — |
| REQ-EVALUATION | evaluation | mandatory | pricing |
| REQ-ACCEPTANCE | acceptance | mandatory (three gates) | test_plan |
| REQ-HANDOVER | knowledge | recommended | team_roles |

Criteria: `CRT-TECH` technical, weight 0.6; `CRT-FIN` financial, weight 0.4 (sum 1). Required response sections: problem understanding, architecture, work plan, team roles, employer dependencies, test plan, pricing.

Knowledge links:

| Link | Node | Executor | Requirements |
|---|---|---|---|
| LNK-ARCHITECTURE | N-SW-WEB | EX-NAZANIN-FARAHANI | REQ-ARCHITECTURE |
| LNK-INTERFACE | N-SW-WEB | EX-HANIEH-SAADATI | REQ-ACCEPTANCE |
| LNK-DESIGN | N-SW-UX | EX-YASAMAN-KARAMI | REQ-ACCEPTANCE |
| LNK-SUPPORT | N-SW-SUP | EX-NILOUFAR-AHMADI | REQ-HANDOVER |
| LNK-LEGAL | N-ADM-LEG | EX-MAHSA-JALALI | REQ-EXCLUSIONS |
| LNK-COST | N-ADM-FIN | EX-REZA-ABBASI | REQ-EVALUATION |
| LNK-LIBRARY | N-LIB | — | REQ-RESPONSE, REQ-EVALUATION |

Record ids (`BP-`, `REQ-`, `CRT-`, `LNK-`, `PRP-`) contain no digits, so the Phase 8 fact checker never reads them as numbers or corpus ids. Statements mention only numbers and ids that occur in AR-RFP-025 (and AR-SW-016).

### 2.2 Proposal registry

| Proposal | Vendor | Price (M toman) | Weeks | Technical | Financial | Recorded weighted |
|---|---|---|---|---|---|---|
| PRP-A (A) | Dadeh Pardaz Shafagh | 285 | 7 | 82 | 74 | 78.8 |
| PRP-B (B) | Novin Gozaresh Pars | 240 | 5 | 68 | 86 | 75.2 |

Decision: `PRP-A`, for quality and compatibility with AR-SW-016 and the Django codebase. PRP-B carries the recorded evaluator note (test plan and integration with the existing API inadequate). Both carry the clarification requests of AR-RFP-025. Component subscores are not recorded and are not invented.

## 3. Candidate selection

`select_candidates(key, blueprints, categories, targets)` walks the key issues by rank:

1. an issue is **sourcing** when its category is in `candidates.categories` (`procurement`) or it is listed in `candidates.targets` (issue → sub-issue sourced on purpose: `AR-ISS-024 → AR-ISS-024/WEB`);
2. a sourcing issue needs a blueprint that lists it; otherwise the reason is `no_blueprint` and nothing is generated;
3. other key issues are reported as `not_sourcing`.

For cycle 1403-Q2: AR-ISS-024 `target`, AR-ISS-031 `not_sourcing` (schedule), AR-ISS-035 `procurement`. Both sourcing issues map to BP-WEB-REPORTING, so one RFP is written.

## 4. RFP text

`build_rfp` writes **fact lines** and the text from the same values; the text is the fact lines under section headings (`config/prompts/rfp/sections.yaml`), so every number and id in the text is in the facts:

- identity: RFP id, title, owner node, cycle;
- context: per served key issue its rank, score (of 100), top three factors and the reason (configured target / procurement); the sub-issue with its status and owner;
- knowledge gaps on the sub-issue or the served issues (sibling sub-issues are skipped; at most 6);
- every requirement by section in a fixed order, marked mandatory / recommended;
- each criterion with weight (%) and what it considers;
- each knowledge link (node, executor, role).

Judging: the RFP is judged as a Phase 10 summary (`ike_summary`) with the FACTS block as the only source. Citation needs the RFP id, the sub-issue and the served issues; completeness needs the 7 mandatory requirement ids and the gap subjects. An RFP is a document, so the script uses a rule judge whose length limit is `judging.max_rfp_chars` (6000) instead of the summary limit (3000); with the summary limit the English RFP would lose one clarity point (19/20, still accepted).

## 5. Evaluation rubric

```
contribution(c) = round_half_up(score(c) × weight(c), 0.1)
weighted        = round_half_up(Σ score(c) × weight(c), 0.1)      # compute_weighted_score
```

| | CRT-TECH × 0.6 | CRT-FIN × 0.4 | weighted | recorded |
|---|---|---|---|---|
| PRP-A | 82 → 49.2 | 74 → 29.6 | 78.8 | 78.8 |
| PRP-B | 68 → 40.8 | 86 → 34.4 | 75.2 | 75.2 |

Rules: a proposal that misses a required response section is **not compliant** and cannot win; the ranking orders by weighted score (ties by id); the **winner** is the top compliant proposal; the recorded decision must name the winner (`decision_consistent`); every recorded weighted score must equal the computed one (`published_match`). Margin 3.6; PRP-B is the cheapest (price gap 45 M toman) and the fastest (2 weeks shorter) but does not win on price alone.

`ProposalService.audit` returns every problem at once:

| Code | Meaning |
|---|---|
| `unknown_rfp`, `duplicate_id` | registry does not match a blueprint / a proposal id is repeated |
| `unknown_criterion`, `missing_score`, `score_range` | scores do not match the RFP criteria or are outside 0..100 |
| `unknown_section`, `missing_section` | response sections do not match the RFP |
| `unknown_document`, `missing_evidence` | evidence documents |
| `decision_missing`, `decision_unknown` | no decision / selected id not registered |
| `ungrounded_number` | price, duration, a score or the recorded weighted score is not in the evidence text |
| `ungrounded_statement` | feedback, clarifications or decision reason contain an unsupported number or id |
| `published_mismatch` | computed weighted score differs from the recorded one |
| `decision_mismatch`, `no_winner` | decision is not the top compliant proposal / nobody is compliant |

## 6. Automated feedback

`build_feedback` writes, per proposal and language: identity (proposal, label, vendor, RFP, version); weighted score with every contribution and the rank; the winner and the gap (or the lead, for the winner); price and duration against the lowest price and the shortest duration; missing sections; the recorded evaluator note; the clarification requests; the decision reason; and where the result is recorded (`AR-ISS-024/WEB`, `AR-ISS-024`, `AR-ISS-035` in node `N-SW`). It is judged like a summary: citation needs the RFP id and the proposal id; completeness needs the knowledge subjects.

## 7. Links back to node knowledge

`link_knowledge` checks every blueprint link (node exists, executor exists and works in that node, linked requirements exist) and writes the outcome row (RFP, sub-issue, issues, owner node, selected proposal, weighted score, evidence). `knowledge_linked` requires every link valid and an outcome with sub-issue and decision: 7 links, 6 nodes, 6 executors, outcome `AR-ISS-024/WEB ← PRP-A`.

## 8. Negative controls

| Group | Broken copy | Expected code |
|---|---|---|
| blueprint | fabricated document, weights 0.6 + 0.5, 65% instead of 60%, REQ-ACCEPTANCE dropped, owner `N-XXX`, executor on another node, issue `AR-ISS-099` | `unknown_document`, `weights_not_one`, `ungrounded`, `missing_section`, `unknown_node`, `executor_node_mismatch`, `unknown_issue` |
| proposals | financial 84.2 (= 240 / 285 × 100, a price formula), price 250, criterion `CRT-API`, missing score, score 110, test plan dropped, decision `PRP-B`, RFP `AR-RFP-1403-99`, duplicate PRP-A, invented "91" in feedback | `published_mismatch`, `ungrounded_number`, `unknown_criterion`, `missing_score`, `score_range`, `missing_section`, `decision_mismatch`, `unknown_rfp`, `duplicate_id`, `ungrounded_statement` |
| RFP text (2 languages) | invented number, invented id, lines with the linked ids removed | judge rejects |
| feedback (2 proposals × 2 languages) | same three | judge rejects |

A control counts as rejected only when it is rejected **for the expected reason**.

## 9. Live step (advisory)

With Ollama and `qwen3:8b`: an RFP summary (`summary` + up to 3 `questions`) and feedback for the runner-up (`feedback`) in Persian and English, JSON replies, think off. Each reply is parsed (`json` / `json_extracted`), fact-checked against the facts (numbers and ids), checked for invented RFP / issue / proposal / requirement / criterion ids, and judged by the rule judge and `qwen3:8b`; accepted only when every check and every judge accepts. The LLM judge also judges the template feedback of the runner-up. The live step never changes the RFP, the scores, the decision, the CSV files or PASS/FAIL. About 10 model calls.

## 10. Checks

`pytest`, `prior_steps`, `inputs_loaded`, `blueprint_valid`, `evidence_grounded`, `rfp_generated`, `rfp_accepted`, `proposals_valid`, `evaluation_matches_published`, `decision_consistent`, `feedback_accepted`, `knowledge_linked`, `negative_controls_rejected`, `csv_round_trip`. The script prints the `PHASE 13 SUMMARY` block and writes `results/phase-13/rfp-check-<UTC>.json`; CSV files go to `exports/rfp/<RFP id>/`.

## 11. Results on my system

Run on 2 Azar 1405 at about 23:19 Tehran time (UTC+3:30) on Fedora Linux, Python 3.15.2, i5-12400F, 16 GB RAM, RTX 3060 12 GB, Ollama 0.40.17 with `qwen3:8b`. Status **PASS**, all 14 checks ok.

```text
======== PHASE 13 SUMMARY ========
status: PASS
kit: rag-core 0.13.0 (phase 13 rfp generation, proposal management)
python: 3.15.2
pytest_exit: 0
pytest_passed: 1355
pytest_failed: 0
pytest_errors: 0
pytest_skipped: 0
prior_steps: ingest=0 dedup=0 hierarchy=0 issues=0 rag=0 ike=0 judge=0 transfer=0 projects=0
inputs: cycle=1403-Q2 key=AR-ISS-024,AR-ISS-031,AR-ISS-035 gaps=14 blueprints=1 proposals=2 executors=15
rfp_candidates: key=3 sourcing=2 (AR-ISS-024:target->BP-WEB-REPORTING,AR-ISS-035:procurement->BP-WEB-REPORTING) none=1 (AR-ISS-031:not_sourcing) rfps=1
blueprint: BP-WEB-REPORTING rfp=AR-RFP-1403-07 requirements=11 (mandatory=7) criteria=2 weights=60+40 links=7 problems=0
evidence: blueprint fa=18/18 en=18/18 weights fa=2/2 en=2/2
evidence: proposals numbers fa=2/2 en=2/2 statements fa=4/4 en=4/4
rfp AR-RFP-1403-07 fa: sections=11 requirements=11 issues=AR-ISS-024,AR-ISS-035 gaps=1 words=569 chars=3679 rule=20 accepted
rfp AR-RFP-1403-07 en: sections=11 requirements=11 issues=AR-ISS-024,AR-ISS-035 gaps=1 words=528 chars=4232 rule=20 accepted
evaluation: PRP-A weighted=78.8 (CRT-TECH 82x0.6=49.2 + CRT-FIN 74x0.4=29.6) published=78.8 match=yes rank=1 compliant=yes price=285 weeks=7
evaluation: PRP-B weighted=75.2 (CRT-TECH 68x0.6=40.8 + CRT-FIN 86x0.4=34.4) published=75.2 match=yes rank=2 compliant=yes price=240 weeks=5
decision: selected=PRP-A winner=PRP-A consistent=yes margin=3.6 cheapest=PRP-B price_gap=45 fastest=PRP-B duration_gap=2 published_match=2/2
feedback PRP-A fa: chars=612 rule=20 accepted
feedback PRP-A en: chars=724 rule=20 accepted
feedback PRP-B fa: chars=718 rule=20 accepted
feedback PRP-B en: chars=853 rule=20 accepted
knowledge: links=7 valid=7 nodes=6 executors=6 outcome=AR-ISS-024/WEB<-PRP-A
negative_controls: blueprint rejected=7/7 proposals rejected=10/10 rfp_text rejected=6/6 feedback rejected=12/12 by_kind=wrong_number:6/6,fabricated_id:6/6,drop_items:6/6
csv: files=5 dir=exports/rfp/AR-RFP-1403-07 round_trip_problems=0
live: ok
live_ai: model=qwen3:8b think=off format=json generated=4 parse_errors=0 grounded=4/4 invented_ids=0 accepted=2/4
live_judge: ai rule=2/4 llm=3/4 combined=2/4 feedback_templates llm=2/2
  rfp_summary AR-RFP-1403-07 fa: accepted mentioned=3/4 rule=18 llm=18
  feedback PRP-B fa: accepted mentioned=2/2 rule=20 llm=20
  rfp_summary AR-RFP-1403-07 en: rejected mentioned=2/4 rule=16 llm=15
  feedback PRP-B en: rejected mentioned=1/2 rule=15 llm=20
live_timings: generate_avg_s=5.175 tokens_avg=1226+260 total_s=31.5
checks: pytest=ok prior_steps=ok inputs_loaded=ok blueprint_valid=ok evidence_grounded=ok rfp_generated=ok rfp_accepted=ok proposals_valid=ok evaluation_matches_published=ok decision_consistent=ok feedback_accepted=ok knowledge_linked=ok negative_controls_rejected=ok csv_round_trip=ok
results_json: /home/mdhdl/Desktop/RAG/results/phase-13/rfp-check-20261123T194948Z.json
======== END PHASE 13 SUMMARY ========
```

| item | expected | actual |
|---|---|---|
| tests | 1207 + 148 = 1355 | 1355 passed, 0 failed, 0 errors, 0 skipped |
| inputs | 3 key issues, 14 gaps, 15 executors | same |
| candidates | AR-ISS-024 (target), AR-ISS-035 (procurement) sourced; AR-ISS-031 not | same; 1 RFP (AR-RFP-1403-07) |
| blueprint | 11 requirements (7 mandatory), weights 60+40, 7 links, 0 problems | same |
| evidence | 18/18, 2/2; proposals 2/2, 4/4 per language | same in fa and en |
| RFP text | rule 20, accepted | fa 20 and en 20, accepted (11 sections, 1 gap) |
| PRP-A | 78.8 | 78.8, matches published |
| PRP-B | 75.2 | 75.2, matches published |
| decision | PRP-A, consistent | PRP-A, consistent, margin 3.6 |
| feedback | 4 texts, rule 20 | 4 texts, rule 20, accepted |
| knowledge | 7/7 links, 6 nodes, 6 executors | same |
| negative controls | 7/7, 10/10, 6/6, 12/12 | same |
| CSV | 5 files, 0 problems | 5 files, 0 problems |
| live advice | optional | 4 generated, 0 parse errors, 4/4 grounded, 0 invented ids, accepted 2/4 |

Notes:

* Every predicted line matched. Sourcing selected AR-ISS-024 (set target) and AR-ISS-035 (procurement); AR-ISS-031 is a schedule issue and was not sourced.
* The weighted scores reproduce the published ones exactly, and the recorded decision (PRP-A) agrees with the ranking. PRP-B was cheaper (45 million toman less) and faster (2 weeks sooner) but lost on the technical score.
* The template RFP and all four feedback letters scored 20/20. All 35 negative controls were rejected with the expected codes.
* The AI texts invented nothing. Both Persian texts were accepted (RFP summary rule 18 / LLM 18, PRP-B feedback 20 / 20). Both English texts were rejected because they left out required ids: the RFP summary named 2 of 4 items (rule 16, LLM 15) and the PRP-B feedback named 1 of 2 (rule 15, LLM 20). Under the combined rule (both judges must accept) the result is 2/4. The LLM judge accepted both template feedback letters (2/2). The advice has no effect on the RFP, the scores, the decision or the exports.
* Live timings: about 5.2 s per generation, about 1226 prompt + 260 completion tokens, 31.5 s in total.
* Results file: `results/phase-13/rfp-check-20261123T194948Z.json`.

## 12. Limitations

- One blueprint. A new sourced issue needs a reviewed, grounded blueprint first; without it the system reports `no_blueprint`.
- Only the two recorded subscores exist; component subscores are not invented.
- Scores come from human evaluators; the system reproduces the arithmetic and checks the decision, it does not grade proposal quality.
- AI texts are advice only.
