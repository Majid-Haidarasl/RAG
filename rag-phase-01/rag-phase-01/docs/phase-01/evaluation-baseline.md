# Phase 1 — Evaluation Metrics Baseline

Status: **initial — pending supervisor review.** All targets below are proposals for discussion; spec section 19 allows the team to adjust them with the supervisor. No values have been measured yet; measurement starts in the phase listed for each metric.

Sources: specification section 19.1 (component matrix, 44 components), 19.2 (model and prompt metrics, 8 areas), section 16 (judge rubric and 18/20 threshold).

## 1. Component metrics (spec 19.1)

| ID | Component | What is measured | Success criterion (spec) | Initial target (pending supervisor review) | Method | Measured in phase |
|---|---|---|---|---|---|---|
| C-01 | DDD architecture | Bounded contexts, aggregates, entities, VOs, domain services, repositories, application services defined | Architecture document names every core concept and maps each use case to a context | 100% of the 12 use cases in `bounded-contexts-draft.md` mapped; every glossary term owned by one context | Document review with supervisor | 3 |
| C-02 | Node definition | Node can be registered with name, domain, layer, parent, attributes, reporting rule | All required node fields are created, updated, retrieved and validated in unit tests | 21/21 sample nodes load from `node-registry.sample.csv` without validation error; each required field has a failing-input test | Unit tests | 6 |
| C-03 | Layer registry | Companies/units assigned to layers | Every configured entity has exactly one valid primary layer and valid parent–child links | 0 orphan nodes; 0 cycles; parent layer = child layer − 1 (except repository nodes) | Unit tests on sample registry | 6 |
| C-04 | Node boundary | Internal structure of a node can be excluded | A node can be marked leaf without mandatory sub-structure | All 15 L3 nodes and `N-LIB` accepted as leaf nodes | Unit tests | 6 |
| C-05 | DOC ingestion | DOC files registered and text extracted via chosen conversion | Sample DOC files become retrievable KnowledgeItems with metadata | ≥ 95% of sample DOC files ingested; failures logged with reason | Ingestion run on converted corpus sample (adapter tested with fakes) | 4 |
| C-06 | DOCX ingestion | DOCX processed with structure and metadata | Sample DOCX files produce chunks with source references | 52/52 corpus files ingested; 100% of chunks carry document ID, version and heading path | Ingestion run + unit tests on parser rules | 4 |
| C-07 | PDF ingestion | Text and page references extracted from PDF | Sample PDFs produce retrievable chunks with page references where possible | ≥ 95% of PDF chunks carry a page number | Ingestion run on PDF exports of corpus | 4 |
| C-08 | LVM-assisted interpretation | Visual/layout documents can be flagged for LVM | Selected documents are sent to the LVM adapter and output is stored | 100% of flagged documents routed to `LvmPort`; output linked to source version | Unit tests with fake LVM | 4 |
| C-09 | Knowledge metadata | Metadata recorded for documents, issues and generated knowledge | Required metadata validated and usable as retrieval filters | 100% of corpus items have node, document type, version, confidentiality, language | Unit tests + ingestion report | 5 |
| C-10 | Knowledge versioning | New version on update; history kept | Update creates a new active version without deleting the previous one | Exactly one active version per KnowledgeItem; 0 deleted versions | Unit tests | 5 |
| C-11 | Knowledge chunking | Long/complex knowledge split into chunks | Chunking keeps source ID, version ID, order and section/page reference | 100% of chunks keep the four fields; no chunk crosses a top-level section boundary | Unit tests on boundary rules | 5 |
| C-12 | Duplicate detection | Exact and near duplicates detected | Identical hashes and similarity above agreed threshold detected | Exact: 100% recall on planted duplicates; near: ≥ 0.90 recall at initial cosine threshold 0.95 | Unit tests + planted-duplicate set | 5 |
| C-13 | Overlap detection | Partial overlaps detected | Chunk-level similarity above threshold is flagged | Azarpakhsh contract-split passages in AR-FIN-008, AR-FIN-010, AR-ISS-024, AR-TRN-026 flagged as overlap (not duplicate); FA/EN pairs not flagged as duplicates | Unit tests + corpus run | 5 |
| C-14 | Embedding index | Embeddings generated and chunks retrieved | Sample queries return relevant chunks within agreed Top-K | Recall@5 ≥ 0.80 on the golden question set | Evaluation set (see section 3) | 8 |
| C-15 | RAG context assembly | Retrieved knowledge prepared for the model | Assembly respects node scope, source limits and prompt template needs | 0 out-of-scope chunks in assembled context; context ≤ configured token budget | Unit tests | 8 |
| C-16 | Question answering | Answers grounded in node knowledge | Answers include source references and declare uncertainty when knowledge is missing | Citation correctness ≥ 0.90; abstention on no-evidence questions ≥ 0.90 | Evaluation set + judge | 8 |
| C-17 | Offline operation | Models and retrieval run without internet | Core RAG workflows run in the offline target with local models and data | 100% of core workflows run with network disabled | Manual demonstration (not a unit test) | 2 |
| C-18 | Small-model management | Embedding, LLM, LVM registered and evaluated | Model registry includes selected model, task, limits and evaluation notes | 1 registry entry per task type (embedding, QA/summary LLM, judge LLM, LVM) with notes | Document review | 2 |
| C-19 | Prompt management | Prompts versioned and linked to task type | Templates have version, task, output structure and unit-tested assembly rules | 100% of the 12 prompt categories in spec 8.3 have a versioned template and an assembly test | Unit tests | 14 |
| C-20 | Cyclic processing | Logical trigger defined and node processing executed | Trigger workflow prepares updated node package and stores the latest version | Each trigger type (phase completion, change batch, upper-layer request) produces one stored package in tests | Unit tests with fakes | 11 |
| C-21 | CSV output | Transfer data exported to CSV | CSV contains agreed columns and passes formatting tests | 100% of packages round-trip CSV → object without loss; UTF-8 with Persian text intact | Unit tests | 11 |
| C-22 | Database storage | Transfer package stored in local DB | Latest accepted package retrievable by node and reporting phase | Query by (node, period) returns exactly one latest accepted package | Unit tests with in-memory repository | 11 |
| C-23 | Upward transfer | Upper layer requests latest child package | Request returns latest accepted package, score, version ID and source node identity | 100% of responses contain the four fields; failed latest package triggers warning + previous accepted | Unit tests | 11 |
| C-24 | Detail-level adaptation | Output adapted to receiving layer | Same source yields executive, managerial and technical summaries at different detail | 4 levels generated for the Azarpakhsh case; judge detail-fit criterion ≥ 2.5/3 at each level | Evaluation set + judge | 11 |
| C-25 | Transfer improvement suggestion | AI suggests adding/reducing/changing detail | Suggestion identifies missing, excess or unsuitable information | ≥ 0.80 of planted defects (e.g., penalty waiver stated as approved) detected | Planted-defect set | 11 |
| C-26 | Project tracking | Completed projects, research, achievements, challenges, unresolved issues modeled | Project record links research, achievements, challenges, unresolved issues, knowledge and executors | 3/3 corpus projects (Azarpakhsh, Rahavard Sanat, Dashtpakhsh) modeled with all links | Unit tests on sample data | 12 |
| C-27 | Issue creation | Issue created with metadata | Creation includes title, description, metadata, priority, status and node ownership | Missing required field → validation error in 100% of tests | Unit tests | 7 |
| C-28 | Issue comparison | New issue compared with existing issues | Probable duplicate/related issues above similarity threshold are identified | Precision ≥ 0.80 on a planted similar-issue set | Evaluation set | 7 |
| C-29 | Sub-issue decomposition | Issue split into sub-issues | Sub-issues stored as issues with parent relation and relative position | AR-ISS-024 rebuilt with 3 sub-issues (HW, WIN, LEG), correct parent and order | Unit tests | 7 |
| C-30 | Issue–knowledge comparison | Issue compared with node knowledge | Related documents, gaps and prior answers returned for sample issues | For AR-ISS-024 sub-issues, ≥ 80% of the related documents listed in the issue file are retrieved | Evaluation set | 8 |
| C-31 | Executor analysis | Executors and expertise analysed | Candidates identified from profile metadata, project links and knowledge links | Top-1 suggestion matches the proposed executor in AR-ISS-024 for 3/3 sub-issues; no suggestion outside allowed referral domain | Unit tests + evaluation set | 9 |
| C-32 | IKE model | Relations created, retrieved, summarized | Model records relation type, confidence, source and creating version | 100% of relations have the four attributes; all 12 relation types supported | Unit tests | 9 |
| C-33 | Possible solution | Probable answer generated from knowledge | Answer includes source references, limitations and score or confidence | 100% of answers contain the three elements; judge ≥ 18/20 on important cases | Evaluation set + judge | 8 |
| C-34 | Issue progress | Status and progress computed | Progress follows agreed deterministic rules and is unit-tested | Same inputs → same percentage in 100% of runs; every rule has a test | Unit tests | 7 |
| C-35 | Key-issue prioritization | Important issues ranked | Ranking uses agreed criteria and is stable for sample data | Identical ranking across repeated runs; Azarpakhsh ranked first among corpus issues | Unit tests | 12 |
| C-36 | Research gap detection | Insufficient or missing knowledge detected | Issues with weak evidence, outdated or conflicting knowledge, or failed judge score are flagged | Both AR-TRN-026 gaps (photo-based part detection, repair-retrieval quality) flagged from corpus evidence | Evaluation set | 12 |
| C-37 | RFP generation | RFP generated from issue and requirements | RFP includes goal, scope, outputs, evaluation criteria, constraints and source issue link | 100% of mandatory sections present (spec 19.2) | Unit tests on RFP structure | 13 |
| C-38 | Proposal management | Proposals registered against RFP | Proposal record links RFP, provider, metadata, evaluation status and feedback | AR-RFP-025 bids A and B registered with all links | Unit tests | 13 |
| C-39 | Proposal evaluation | Proposals scored against RFP criteria | Evaluation output includes score and explanation per criterion | Weighted scores reproduce 78.8 (A) and 75.2 (B) from 60/40 weights | Unit tests | 13 |
| C-40 | Feedback generation | Automatic feedback for proposals | Feedback states strengths, weaknesses, missing requirements, risks, fix suggestions | 100% of major critiques reference a criterion or proposal section | Evaluation set + judge | 13 |
| C-41 | LLM as judge | Outputs scored on source, request and rubric | Important outputs must score ≥ 18/20 unless accepted after manual review | Judge–human agreement within ±2 points on ≥ 80% of a 20-item reviewed sample | Human-reviewed sample | 10 |
| C-42 | Architecture as knowledge | System structure and IKE represented as node knowledge | Upper node can receive a summarized view of lower-node issues and relations | L1 package for Azarpakhsh lists all 3 sub-issues with knowledge/executor status | Unit tests + evaluation set | 11 |
| C-43 | Source referencing | Generated outputs cite source knowledge | Answers and packages include source ID or document reference | 100% of answers and packages contain ≥ 1 valid SourceReference; 0 references to non-existent IDs | Unit tests + evaluation set | 8 |
| C-44 | Unit testing | Domain and application logic covered | Unit test suite runs for selected modules and covers important rules | All tests pass offline in < 2 minutes; ≥ 80% line coverage of domain + application layers | pytest + coverage | 15 |

## 2. Model and prompt metrics (spec 19.2)

| ID | Area | Metric | Initial target (pending supervisor review) |
|---|---|---|---|
| MP-01 | Retrieval relevance | Relevance of Top-K chunks to sample questions | Recall@5 ≥ 0.80 and MRR ≥ 0.60 on the golden set (threshold confirmed after baseline run) |
| MP-02 | Answer faithfulness | Answer does not contradict the source | Judge faithfulness criterion ≥ 4/5 on ≥ 90% of answers |
| MP-03 | Summarization quality | Summary keeps essential information at the right detail level | Judge ≥ 18/20 for important transfer summaries |
| MP-04 | Issue decomposition | Sub-issues coherent and actionable | ≥ 80% of decompositions accepted by human review on the sample set |
| MP-05 | Executor matching | Suggested executor aligned with expertise metadata | 100% of match explanations cite a profile, project or document |
| MP-06 | RFP completeness | RFP contains all mandatory sections | 100% of mandatory RFP sections present in generated drafts |
| MP-07 | Proposal feedback | Feedback mapped to RFP requirements | 100% of major critiques reference a criterion or proposal section |
| MP-08 | Prompt stability | Similar structured input yields stable-schema output | 100% of outputs parse against the schema across 5 repeated runs per template; parser and assembly covered by unit tests |

## 3. LLM-judge rubric (spec 16.1)

| Criterion | Points |
|---|---:|
| Faithfulness to source knowledge | 5 |
| Completeness against the user request | 4 |
| Detail level fits the target layer | 3 |
| Correct handling of uncertainty and gaps | 3 |
| Clarity and professional structure | 2 |
| Citability (source references) | 2 |
| No unsupported claim | 1 |
| **Total** | **20** |

Initial threshold: **18/20** for important outputs (TransferPackages to L0/L1, RFPs, issue answers used for decisions). Below threshold the system regenerates, requests/reduces detail, adds citations, flags for human review, or falls back to the last accepted package (spec 16.2).

## 4. Baseline evaluation dataset (to be built in phases 2 and 8)

| Set | Size (initial plan) | Content | Source |
|---|---|---|---|
| Golden Q&A set | 60 questions (30 FA, 30 EN) | Fact, policy, cross-document and node-scope questions with adjudicated relevant chunks and accepted answers | All 26 documents |
| No-evidence set | 10 questions | Questions the corpus cannot answer (e.g., measured accuracy of photo-based part detection) — correct behaviour is abstention | AR-TRN-026 gaps |
| Trap set | 10 questions | Proposal vs. approval confusion, e.g. “Has the penalty been waived?” → proposed, not approved; “Who handles the Windows problem?” → Roozbeh Mohseni, AR-SW-019, AR-ISS-024/WIN | AR-ISS-024, AR-TRN-026 |
| Planted duplicates | 10 pairs | Exact copies, re-saved near duplicates, FA/EN pairs (must not be duplicates) | Corpus copies |
| Transfer set | 4 summaries | Azarpakhsh at executive, managerial, technical-summary, detailed-technical level | AR-TRN-026 as reference |
| Proposal set | 2 bids | Weighted scoring and feedback reproduction | AR-RFP-025 |

Rules: development questions are kept separate from held-out evaluation questions (as required by AR-TRN-026 gap two); no observed numbers are reported before a run; failed results are kept, not deleted.

## 5. Questions for the supervisor

1. Are Recall@5 ≥ 0.80 and MRR ≥ 0.60 reasonable for small local embedding models on a bilingual corpus, or should targets be set only after the phase-8 baseline run?
2. Is 18/20 the threshold for all important outputs, or only for L0/L1 packages (with e.g. 16/20 for L2/L3)?
3. What judge–human agreement level is acceptable (proposed: ±2 points on 80% of a 20-item sample)?
4. Is ≥ 80% coverage of domain + application layers an acceptable unit-test target?
