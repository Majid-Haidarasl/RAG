# Phase 9 — Executor analysis and the Issue-Knowledge-Executor (IKE) model

Kit version 0.9.0. The reference case is **Azarpakhsh** (AR-ISS-024) and its four sub-issues (HW, WIN, WEB, LEG). Phase 9 fills the Phase 3 `executors` and `ike` bounded contexts: executor profiles with expertise metadata (AR-EXE-023), an explainable executor matcher, a comparison between the knowledge an issue cites and the knowledge its owner node can retrieve (Phase 8), and a typed relation graph between issues, sub-issues, knowledge and executors with a fact-checked summary.

No new dependencies. Unit tests use fakes and never need Ollama, the GPU or the internet.

## 1. Where things live

Issue #9 lists `src/executors/…` and `src/ike/…`. Following the earlier phases, the code is in the existing `rag_core.executors` and `rag_core.ike` contexts:

| Issue #9 output | Code |
|---|---|
| executor profiles | `executors/domain/model.py` (`Executor`, `ExpertiseTag`, `ReferralCapacity`), registry `data/executors/executor-registry.json`, loader `executors/infrastructure/registry_json.py`, validator `executors/domain/validation.py` |
| expertise metadata | `executors/domain/expertise.py` (`ExpertiseProfile`, tokenizer, stemmer, stop words) |
| matching | `executors/domain/matching.py` (`ReferralRequest`, `ExecutorMatcher`, `ReferralPlan`), `executors/domain/capacity.py` (`CapacityLedger`), service `executors/application/services.py` |
| ACLs (executors) | `executors/infrastructure/hierarchy_acl.py` (Phase 6 teams), `executors/infrastructure/issues_acl.py` (Phase 7 sub-issues → `ReferralRequest`) |
| issue-knowledge comparison | `ike/domain/comparison.py` (`compare_knowledge`, `IssueKnowledgeComparison`) |
| IKE relations | `ike/domain/model.py` (`IkeGraph`, `IkeRelation`, `RelationType`, `RELATION_RULES`), builder `ike/domain/builder.py` |
| summary generation | `ike/domain/summary.py` (digest, facts, templates, prompt, check), service `ike/application/services.py` (`IkeSummaryService`); prompts in `config/prompts/ike/summary.yaml` |
| ACLs (ike) | `ike/infrastructure/issues_acl.py`, `executors_acl.py`, `retrieval_acl.py` (Phase 8 retriever → `KnowledgeSearchPort`) |
| check script | `scripts/run_ike_check.py` |
| tests | `tests/unit/executors/`, `tests/unit/ike/`, fixtures `tests/fixtures/executors/`, `tests/fixtures/ike/` |

Each context reaches the others only through its ACL modules; the domain packages import nothing from `issues`, `hierarchy` or `rag`.

## 2. Executor profiles (AR-EXE-023)

* 15 executors, one home team node each (13 distinct Phase 6 team nodes, layer 3).
* Expertise metadata: specialty, allowed referral domains (English + Persian), expertise tags, knowledge documents held, outputs, authority limits.
* `ReferralCapacity`: hours per week (0–60) or **unpublished** (`null`) for HR, finance and legal, where AR-EXE-023 says capacity is allocated through unit planning. Unpublished is neither zero nor unlimited; the ledger never books against it.
* Pay and salary are excluded on purpose (confidential HR data).
* `Executor.change_capacity(reason, approved_by)` bumps the profile version (1.0 → 1.1) and records `ExecutorProfileChanged`.
* Names: the issue registry spells `Rouzbeh Mohseni`; the alias resolves to `EX-ROOZBEH-MOHSENI`.

## 3. Executor matching

Text of a request = sub-issue title + scope + acceptance output. Vocabulary of an executor = specialty + allowed referral domains + expertise tags (outputs and authority limits are not used, so a generic word like "report" in an output does not open a domain).

Tokenizer: Latin and Persian letters/digits, lower-case, drop tokens shorter than 2 characters, pure digits and stop words; light stemming (`-ing`, `-ies → -y`, plural `-s`).

| Signal | Value |
|---|---|
| node | 1.0 owner node, 0.6 supporting node, 0 otherwise |
| knowledge | shared documents / request documents |
| domain | min(matched domain terms, 4) / 4 |
| score | 0.4·node + 0.3·knowledge + 0.3·domain |

Roles (at least **two** matching terms are required — a single keyword is not enough, AR-EXE-023):

| Role | Rule |
|---|---|
| `lead_candidate` | home node = owner node and ≥ 2 domain terms |
| `collaborator` | supporting node and (≥ 2 terms or a shared document) |
| `cross_node_candidate` | outside the item's nodes, ≥ 2 terms and a shared document (shown, not recommended) |
| `excluded` | everything else, or 0 published hours |

Order: score desc, matched terms desc, id. Lead = first lead candidate. Acceptance authority: `board` for a reserved decision (AR-ISS-024/LEG), otherwise `team_owner:<owner node>`.

Expected plan for AR-ISS-024 (equal to the executors named in the issue registry):

| Sub-issue | Lead | Collaborators | Authority |
|---|---|---|---|
| HW | Saeed Akbari | Farzaneh Javadi, Ehsan Davari | team_owner:N-HW-REP |
| WIN | Roozbeh Mohseni | — | team_owner:N-SW-WIN |
| WEB | Nazanin Farahani | Hanieh Saadati, Yasaman Karami | team_owner:N-SW-WEB |
| LEG | Mahsa Jalali | Reza Abbasi | board |

Policy cases checked by the script (all must be `excluded`): Kian@WEB (one term), Amin@WEB (mobile), Roozbeh@HW and Kamran@HW (outside the domain), Farzaneh@WIN.

`CapacityLedger` books hours per executor; when the published capacity is exceeded it raises `CapacityExceeded` ("the relevant VP must set priorities").

## 4. Issue-knowledge comparison

For each sub-issue, the query (titles in both languages + scope + acceptance output) is searched from the **owner node** with the Phase 8 retriever (top_k = 8):

| Field | Meaning |
|---|---|
| `covered` | cited in the registry and retrieved |
| `suggested` | retrieved but not cited (candidate knowledge) |
| `missed` | cited, visible from the owner node, not retrieved |
| `outside_scope` | cited but not visible from the owner node |
| `evidence` | best score passes the Phase 8 floor (vector 0.45 when vectors exist, else BM25 3.0) |
| `cited_recall` | covered / visible cited documents |

Offline the comparison is lexical (BM25); the live step repeats it with the hybrid retriever and the Phase 8 index. Only document ids, ranks and scores leave the retriever; outside-scope evidence is reduced to owner nodes.

## 5. IKE relation model

Endpoint kinds by id: issue `AR-ISS-NNN`, sub-issue `AR-ISS-NNN/CODE`, executor `EX-…`, knowledge `AR-XX-NNN`, anything else is a topic (e.g. `gap:no-lead-executor`).

| Type | Source | Target | Built from |
|---|---|---|---|
| `relates_to` | issue, sub-issue | knowledge, issue | cited documents (1.0), suggested documents (0.7 − 0.1 per rank, min 0.3) |
| `part_of` | sub-issue | its own parent issue | structure |
| `depends_on` | sub-issue | sibling sub-issue (no cycles) | `depends_on` codes |
| `can_handle` | executor | issue, sub-issue | referral plan (score as confidence, note "lead"/"collaborator") |
| `evidence_for` | knowledge | executor | cited documents the executor holds |
| `knowledge_lack` | issue, sub-issue | knowledge, issue, topic | see below |
| `similar_issue` | issue, sub-issue | issue, sub-issue | probable duplicate / related issue |
| `blocked_by` | issue, sub-issue | issue, sub-issue | hard blocker (distinct from soft `depends_on`) |
| `executor_worked_on` | executor | issue, sub-issue | prior work history |
| `supports` | knowledge | issue, sub-issue | knowledge that backs an answer path |
| `conflicts` | knowledge | knowledge, issue, sub-issue | contradicting sources or answers |

Knowledge lacks:

* cited document held by no recommended executor → 0.8; if a sub-issue it depends on holds it → 0.4 ("covered through dependency");
* no lead executor → `gap:no-lead-executor` (0.9);
* cited document outside the owner node's scope → 0.6;
* no in-scope evidence → `gap:no-in-scope-evidence` (0.7).

`IkeGraph.validate()` reports duplicates, ill-typed relations, a sub-issue part of another issue, cross-issue dependencies and dependency cycles; `IkeService.build` refuses an invalid graph. `add` stays permissive for the Phase 3 tests; `add_checked` enforces the rules.

Expected registry-only graph for AR-ISS-024: 51 relations — relates_to 23, part_of 4, depends_on 2, can_handle 9, evidence_for 11, knowledge_lack 2 (WIN → AR-HW-015 through the HW dependency, WEB → AR-RFP-025). This count was confirmed on the reference run. The offline and live graphs add suggestions and comparison lacks, so their counts depend on the retrieval result (see the reference run below).

## 6. Summary generation

1. `digest` reads the graph back (lead, collaborators, knowledge, dependencies, lacks per sub-issue).
2. `facts_lines` writes plain fact lines (ids, nodes, statuses, progress 62%, contract AR-CNT-1402-118, customer).
3. Template summary in Persian or English, or an LLM summary (`qwen3:8b`, thinking off) from the same facts.
4. `check_summary` uses the Phase 8 `CitedFactValidator`: every id and number in the summary must appear in the facts; coverage = sub-issue ids mentioned / sub-issues.

Progress: Phase 7 `Issue.progress()` averages the sub-issues; the IKE view uses the recorded physical progress (62%) when the registry has it.

## 7. Check script

`scripts/run_ike_check.py` (called by `scripts/setup_and_test.sh` after the Phase 8 step) loads the registries, matches AR-ISS-024 and the flat issues, compares knowledge offline, builds the registry and offline graphs, writes template summaries, and — only with Ollama and both models — refreshes the Phase 8 index, compares with the hybrid retriever and asks `qwen3:8b` for Persian and English summaries. The live step never changes PASS/FAIL. Results: `results/phase-09/ike-check-<UTC>.json`.

Checks: `pytest`, `prior_steps`, `executor_registry_valid`, `seed_executors_resolved`, `matching_matches_seed`, `referral_policy`, `leads_match_exe023`, `records_built`, `ike_graph_valid`, `ike_graph_consistent`, `template_summaries_grounded`.

## 8. Reference run

Test system: Ubuntu 24.04.5 LTS, Python 3.12.3; project at `~/Desktop/RAG`. Ollama 0.40.2, embedding `bge-m3:latest`, generation `qwen3:8b` (think off).

- Run: 2026-11-19 00:01:13 UTC (2026-11-19 03:31 Tehran time).
- Result: `status: PASS`, 788 passed, 0 failed, 0 errors, 0 skipped (29.32 s); earlier steps ingest, dedup, hierarchy, issues and rag all exited 0.
- Executors: 15 total, 13 home nodes, 12 published capacities, 3 unpublished; 0 validation errors, 3 warnings.
- Matching for AR-ISS-024: 4 sub-issues, 9 recommended, 9 named, seed agreement 4/4, precision 1.0, recall 1.0.
  - HW lead Saeed Akbari, collaborators Farzaneh Javadi and Ehsan Davari, authority `team_owner:N-HW-REP`.
  - WIN lead Roozbeh Mohseni, no collaborator, authority `team_owner:N-SW-WIN`.
  - WEB lead Nazanin Farahani, collaborators Hanieh Saadati and Yasaman Karami, authority `team_owner:N-SW-WEB`.
  - LEG lead Mahsa Jalali, collaborator Reza Abbasi, authority `board`.
- Referral roles: 5 lead candidates, 4 collaborators, 0 cross-node candidates, 51 excluded. All five policy cases were excluded (Kian@WEB, Amin@WEB, Roozbeh@HW, Kamran@HW, Farzaneh@WIN).
- Executor load: 9 of 15 executors received a referral. Flat issue matching: 6 issues, 4 with a lead.
- Offline knowledge comparison (lexical): cited recall@8 = 0.875, covered 5/10, suggested 11, cited outside scope 4, with evidence 4/4.
- Registry graph: 51 relations (relates_to 23, can_handle 9, evidence_for 11, knowledge_lack 2, depends_on 2, part_of 4).
- Offline graph: 65 relations (relates_to 34, can_handle 9, evidence_for 11, knowledge_lack 5, depends_on 2, part_of 4).
- Knowledge lacks: HW → AR-HW-013, HW → AR-HW-015, WIN → AR-HW-015, WEB → AR-RFP-025, LEG → AR-FIN-010.
- Template summaries: Persian and English both grounded, coverage 4/4, 20 claims each.
- Live step: `ok`. Index: 1219 active, 0 newly embedded, 1219 reused, dim 1024, build 0.135 s (Phase 8 index reused).
- Live knowledge comparison (hybrid): cited recall@8 = 1.0, covered 6/10, suggested 9, with evidence 4/4, search average 0.0657 s.
- Live graph: 63 relations (relates_to 32, can_handle 9, evidence_for 11, knowledge_lack 5, depends_on 2, part_of 4).
- Live Persian summary: grounded, 0 unsupported, coverage 4/4, 426 characters, generation 4.309 s, tokens 995+219.
- Live English summary: grounded, 0 unsupported, coverage 4/4, 1001 characters, generation 5.828 s, tokens 861+312.
- Live timings: total 12.4 s. All 11 checks ok.
- Results file: `results/phase-09/ike-check-20261119T000113Z.json`.

The live cited recall improved from 0.875 (lexical) to 1.0 (hybrid). Both model summaries were grounded and covered all four sub-issues.

## 9. Open points

* Matching is lexical over expertise metadata; synonyms not in the tags are not matched.
* Capacity for HR, finance and legal stays unpublished until unit planning sets it.
* Suggested documents are candidates only; the team owner decides whether to cite them.
