# Phase 1 — Domain Discovery Report

Project: offline hierarchical RAG core for organizational knowledge management, issue management and managerial knowledge transfer
Phase: 1 — Project kickoff and domain discovery
Version: 0.1 (for supervisor review) · Date: 9 November 2026 (18 Aban 1405)
Inputs: project specification (Persian, sections 1–26) · ArmanRayan IT corpus (`corpus/`, 26 FA + 26 EN DOCX + manifest)

---

## 1. Purpose of this report

This report closes phase 1. It fixes the project goals and study scope, the case-study domain, the initial layer and node structure, the sample document inventory, key use cases, and the risks and questions that must be settled with the supervisor before phase 2 (offline models) and phase 3 (DDD architecture). It is the reference for the other phase-1 outputs:

| Output | File |
|---|---|
| Initial glossary (bilingual) | `docs/phase-01/glossary.md` |
| Bounded contexts draft | `docs/phase-01/bounded-contexts-draft.md` |
| Layer / node registry templates and samples | `data/registry/*.csv` |
| Evaluation metrics baseline | `docs/phase-01/evaluation-baseline.md` |
| Unit-test policy | `docs/phase-01/unit-test-policy.md` |
| Sample corpus | `corpus/` |

## 2. Project goals

The goal is a software core — not a separate backend or frontend product — in which every organizational node can manage its own knowledge, model its issues, identify executors and their expertise, prepare summarized and judged knowledge for higher layers, and answer questions from its controlled knowledge, all with small local models and no internet.

Goals grouped from spec section 2 (20 goals):

| Group | Goals (spec numbering) | What “done” means for this project |
|---|---|---|
| G1 Architecture | 1, 17 | DDD core with 10 bounded contexts; the IKE model and architecture are themselves node knowledge |
| G2 Offline RAG | 2, 12 | Retrieval and generation with local Embedding/LLM/LVM; grounded answers with citations |
| G3 Ingestion & knowledge lifecycle | 3, 16, 18, 19 | DOC/DOCX/PDF ingestion, metadata, versioning, chunking, duplicate/overlap detection, any subject domain |
| G4 Hierarchy | 4, 5, 8 | Layer and node registry; each layer defines what it needs from its children |
| G5 Upward transfer | 6, 9, 10 | AI-assisted detail adjustment; cyclic processing; latest package in CSV/DB; offline pull by upper layer |
| G6 Issues & executors | 7, 11, 13, 14 | Issue/sub-issue modeling, IKE relations, progress, key issues, research gaps, project records |
| G7 RFP | 15 | RFP generation, proposal evaluation, automatic feedback |
| G8 Evaluation | 20 | Measurable metrics per component, reviewed with the supervisor; LLM judge with 18/20 threshold |

## 3. Study scope

### 3.1 In scope (spec 4.1)

- Offline RAG core runnable without internet.
- Ingestion of local DOC, DOCX and PDF files.
- Small local Embedding models (retrieval), LLMs (summary, Q&A, issue analysis, RFP, feedback, judging) and LVMs (layout/visual interpretation when needed).
- Node definition and layer registry.
- Knowledge lifecycle: metadata, versioning, chunking, duplicates and overlaps.
- Issue, sub-issue and executor modeling; IKE relations.
- Cyclic node processing and upward TransferPackages stored as CSV or local DB.
- LLM-as-judge evaluation.
- Unit tests for domain logic, application services, scoring, chunking, relation building and prompt assembly.
- Technical documentation, evaluation metrics and presentable outputs.

### 3.2 Out of scope (spec 4.2)

- A separate backend or frontend product; cloud model hosting; internet-dependent processing.
- Complex enterprise identity integration; real-time synchronization between nodes.
- Integration, end-to-end, load, penetration or automated UX testing.
- Training large foundation models; guaranteeing absolute correctness beyond citation, quality control and judge scoring.

### 3.3 Case-study domain decision

The case study is **ArmanRayan Information Technology Company**, a fictional private joint-stock company founded in 1396/2017 with headquarters in Tehran and about 85 staff (52 software and software support, 18 hardware, 15 administrative/financial/legal). It provides computer hardware services (sales, purchase advice, assembly, repair) and enterprise software services (web, mobile, Windows, product design, support).

Why this domain fits the specification:

- It has a natural 5-layer hierarchy (board → CEO → deputies → teams → knowledge library) matching spec section 6.2.
- It mixes technical knowledge (repair, engineering standards), policy knowledge (HR, legal, finance), personnel/executor knowledge and project knowledge — the knowledge types of spec 7.1.
- One flagship cross-unit issue (Azarpakhsh warehouse system) exercises issue decomposition, IKE relations, executor matching, upward transfer at four detail levels, and an RFP with two evaluated proposals.
- All documents exist offline in both Persian and English, which tests bilingual retrieval.
- Everything is fictional: no real personal or confidential data enters the project.

An earlier game-based domain (Dota) was rejected because the RAG would need live game data and continuous querying, which contradicts the offline, document-centred design.

## 4. Assumptions (spec 4.3, refined)

| # | Assumption |
|---|---|
| A1 | The 26-document bilingual ArmanRayan corpus is the initial sample set; more documents (including DOC and PDF) can be derived from it. |
| A2 | All models run locally on a single machine; the target environment has no internet. |
| A3 | The output is a software core with ports for future UIs, not a user-facing application. |
| A4 | Evaluation is based on the metrics in `evaluation-baseline.md`, adjusted with the supervisor. |
| A5 | The final list of nodes per layer is the 21-node ArmanRayan structure in `node-registry.sample.csv`; teams are leaf nodes. |
| A6 | Corpus facts (names, numbers, dates, IDs) are fixed by `shared-facts.md`; the corpus version is 1.0, Mehr 1403 / October 2024, status Approved. |
| A7 | Persian and English versions of a document carry the same content and the same document ID. |

## 5. Stakeholders

| Stakeholder | Role in the project | Interest |
|---|---|---|
| Student / project team (Majid Haidarasl) | Designs, implements and documents the core | Feasible scope, clear metrics, defensible results |
| Supervisor / evaluation team | Reviews scope, metrics, architecture and results | Measurable outcomes, academic rigour |
| Case-study roles (fictional) | Represent users of the core | — |
| · Board (L0), chaired by Dr. Nima Yazdani | Receives executive TransferPackages | Risks, decisions requested, key issues |
| · CEO Eng. Arash Moradi (L1) | Receives managerial packages; resolves cross-deputy conflicts | Project status, cost/time impact |
| · Deputies Maryam Nouri, Behrouz Karimi, Shahab Amini (L2) | Receive technical summaries | Dependencies, capacity, technical decisions |
| · Team leads and specialists (L3) | Own detailed knowledge and issues; act as executors | Grounded answers, correct referral |
| · Knowledge Library (L4) | Holds citable evidence | Provenance and versioning |

## 6. Sample document inventory

26 documents × 2 languages = **52 DOCX files**, plus `manifest.md`. Approximate size: 54,100 words (FA) and 54,709 words (EN); 80 tables per language. All files: version 1.0, Mehr 1403 / October 2024, status Approved.

| # | ID | Title (EN) | Knowledge class | Owner layer / node | Words FA / EN | Tables | Main use in the RAG study |
|---|---|---|---|---|---|---|---|
| 1 | AR-ORG-001 | Company introduction, mission, history, services, layer map | Policy & organization | L0–L1 / Board, CEO | 2,216 / 2,112 | 1 | Corporate context; layer map source |
| 2 | AR-ORG-002 | Full organizational structure | Policy & organization | L1–L3 / CEO, deputies, teams | 2,592 / 2,443 | 1 | Primary source for node registry |
| 3 | AR-BRD-003 | Board of directors bylaws | Governance | L0 / Board | 2,218 / 2,166 | 1 | Approval limits; L0 transfer needs |
| 4 | AR-HR-004 | Hiring policy | HR policy | L2–L3 / Admin deputy, HR unit | 2,240 / 2,151 | 1 | Procedural Q&A |
| 5 | AR-HR-005 | Leave and attendance policy | HR policy | L2–L3 / Admin deputy, HR unit | 2,249 / 2,174 | 1 | Numeric-limit Q&A (26 days, 16 h/month) |
| 6 | AR-HR-006 | Compensation and raise policy | HR policy | L2–L3 / Admin deputy, HR unit | 2,307 / 2,260 | 2 | Approval-threshold Q&A (15% / 25%) |
| 7 | AR-HR-007 | Talent acquisition and retention | HR policy | L2–L3 / Admin deputy, HR unit | 2,294 / 2,195 | 1 | Knowledge-exit and succession knowledge |
| 8 | AR-FIN-008 | Quarterly financial report for the board | Financial report | L0–L1 / Board, CEO (prepared by finance) | 3,133 / 3,258 | 8 | Executive-level reference summary; overlap source |
| 9 | AR-LEG-009 | Legal unit procedure | Legal procedure | L3 / Legal and Contracts Unit | 2,931 / 3,125 | 4 | Legal sub-issue knowledge |
| 10 | AR-FIN-010 | Project accounting and financial workflow | Financial procedure | L3 / Accounting and Finance Unit | 2,790 / 3,012 | 5 | Cost-centre metadata; overlap source |
| 11 | AR-HR-011 | Code of professional ethics and internal rules | HR policy | L2–L3 / Admin deputy, HR unit | 2,588 / 2,802 | 5 | Confidentiality rules |
| 12 | AR-HW-012 | Hardware repair instruction | Hardware procedure | L2–L3 / Hardware deputy, Repair team | 2,096 / 2,215 | 3 | Hardware sub-issue knowledge |
| 13 | AR-HW-013 | Hardware procurement advisory guide | Hardware procedure | L2–L3 / Hardware deputy, Advisory team | 1,960 / 2,109 | 4 | Hardware sub-issue knowledge |
| 14 | AR-HW-014 | Hardware sales process | Hardware procedure | L2–L3 / Hardware deputy, Sales team | 1,945 / 2,085 | 3 | Discount-limit Q&A |
| 15 | AR-HW-015 | Assembly, test and delivery standard | Hardware procedure | L2–L3 / Hardware deputy, Assembly team | 2,051 / 2,134 | 5 | Joint-test evidence knowledge |
| 16 | AR-SW-016 | Software engineering and architecture standards | Software standard | L2 / Software deputy | 1,641 / 1,626 | 2 | Capability-vs-node rule; RFP decision basis |
| 17 | AR-SW-017 | Web development team guide | Team guide | L3 / Web-development Team | 1,624 / 1,625 | 2 | Web team knowledge |
| 18 | AR-SW-018 | Mobile development team guide | Team guide | L3 / Mobile-development Team | 1,652 / 1,645 | 2 | Mobile team knowledge |
| 19 | AR-SW-019 | Windows desktop software team guide | Team guide | L3 / Windows and Desktop Team | 1,656 / 1,661 | 2 | Windows sub-issue knowledge |
| 20 | AR-SW-020 | UI/UX design guide | Team guide | L3 / UX and Interface Team | 1,659 / 1,659 | 2 | Design knowledge |
| 21 | AR-SW-021 | Visual identity and logo design guide | Team guide | L3 / Visual Identity Team | 1,656 / 1,683 | 2 | IP/ownership knowledge |
| 22 | AR-SW-022 | Software SLA and support | Service level | L3 / Support and Deployment Team | 1,652 / 1,669 | 2 | SLA numeric Q&A |
| 23 | AR-EXE-023 | Sample executor profiles | Executor knowledge | L3–L4 / Teams, Knowledge Library | 1,999 / 1,912 | 15 | Executor registry seed (15 profiles) |
| 24 | AR-ISS-024 | Azarpakhsh organizational issue file | Issue file | L4 / Knowledge Library (refers to L3) | 1,656 / 1,642 | 2 | Issue + 3 sub-issues; IKE reference |
| 25 | AR-RFP-025 | Sample RFP and proposal evaluation sheet | RFP & evaluation | L2–L3 / Software deputy, Legal unit | 1,626 / 1,672 | 1 | RFP/proposal reference (78.8 vs 75.2) |
| 26 | AR-TRN-026 | Multi-layer knowledge-transfer report and annual scorecard | Knowledge transfer | L0–L4 / Board to Library | 1,669 / 1,674 | 3 | Reference TransferPackage at 4 detail levels; 2 research gaps |

Coverage against spec 7.1 knowledge types:

| Knowledge type (spec 7.1) | Covered by |
|---|---|
| Technical documents with embedded knowledge | AR-HW-012..015, AR-SW-016..022 |
| Research/implementation documentation | AR-TRN-026 (research gaps), AR-SW-016 |
| Answers to previous issues | AR-ISS-024 (corrective knowledge) |
| General information on lower units (upper layers) | AR-ORG-001, AR-ORG-002 |
| IKE model as node knowledge | AR-ISS-024 sub-issue table, AR-TRN-026 |
| Personnel profiles | AR-EXE-023 |
| Project reports and completion records | AR-FIN-008, AR-TRN-026 |
| Research records and experiment notes | AR-ISS-024 (evidence sheets), AR-TRN-026 gaps |
| Achievements; challenges and unresolved issues | AR-TRN-026 sections 7–9 |
| RFPs, proposals, evaluations, feedback | AR-RFP-025 |

## 7. Layer and node findings

### 7.1 Layers

| Layer | Name | ArmanRayan content | Nodes |
|---|---|---|---|
| L0 | Strategic governance | Board of directors | 1 |
| L1 | Parent organization | Chief Executive Management and headquarters | 1 |
| L2 | Specialist deputies | Administrative; Hardware; Software | 3 |
| L3 | Execution teams and units | 5 administrative units, 4 hardware teams, 6 software teams | 15 |
| L4 | Internal knowledge repository | ArmanRayan Organizational Knowledge Library | 1 |
| | **Total** | | **21** |

### 7.2 Node tree

```
L0  N-BRD      ArmanRayan Board of Directors (chair: Dr. Nima Yazdani)
L1  └─ N-CEO   Chief Executive Management and Headquarters (Eng. Arash Moradi)
L2     ├─ N-ADM   Administrative and Organizational Resources Deputy (Maryam Nouri)
L3     │   ├─ N-ADM-HR   Human Resources Unit
       │   ├─ N-ADM-FIN  Accounting and Finance Unit
       │   ├─ N-ADM-LEG  Legal and Contracts Unit
       │   ├─ N-ADM-SRV  Administrative and Welfare Services Unit
       │   └─ N-ADM-SEC  Secretariat and Organizational Communications Unit
L2     ├─ N-HW    Hardware and Equipment Services Deputy (Behrouz Karimi)
L3     │   ├─ N-HW-REP   Hardware Repair and Maintenance Team
       │   ├─ N-HW-ADV   Purchasing Advice and Equipment Evaluation Team
       │   ├─ N-HW-SAL   Hardware Sales Team
       │   └─ N-HW-ASM   System Assembly, Testing and Delivery Team
L2     ├─ N-SW    Software and Digital Products Deputy (Shahab Amini)
L3     │   ├─ N-SW-WEB   Web-development Team  [capabilities: Django, Laravel, Node.js, React]
       │   ├─ N-SW-MOB   Mobile-development Team  [Flutter]
       │   ├─ N-SW-WIN   Windows and Desktop Software Team  [C#/.NET]
       │   ├─ N-SW-UX    User Experience and Interface Team
       │   ├─ N-SW-VIS   Visual Identity and Graphics Team
       │   └─ N-SW-SUP   Software Support and Deployment Team
L4     └─ N-LIB   ArmanRayan Organizational Knowledge Library (repository node)
```

### 7.3 Findings that affect the model

1. **Capabilities are not nodes.** AR-ORG-002 s.6 forbids separate Django/React teams. Technologies are tags on nodes and executors. This must be a validation rule in the hierarchy context.
2. **All L3 nodes are leaf nodes.** Their internal structure is not modeled (spec 6.2 allows this); people appear as executors, not nodes.
3. **L4 is a repository, not a decision layer.** It stores evidence for L0–L3 and does not produce its own upward summaries. Its parent link breaks the “parent = layer − 1” rule — see question Q3.
4. **Cost centres map to nodes.** CC-BRD, CC-CEO, CC-ADM, CC-HW (HW-REP/ADV/SAL/ASM), CC-SW (SW-WEB/MOB/WIN/UX/VIS/SUP) and the temporary project code PRJ-AZP-118 (AR-FIN-010) are useful node and project metadata.
5. **Transfer routes and detail levels already exist in the corpus.** AR-TRN-026 defines routes 3→2→1→0 (plus 3↔4) and four audience levels: board (executive), CEO (managerial), software VP (technical summary), web team (detailed technical). This is the reference for TransferPackage tests.
6. **Approval thresholds are numeric and testable:** contracts > 500M toman → CEO, > 2,000M → board; raises up to 15% → VP + CEO, 15–25% → CEO, > 25% → board; sales discounts 3% / 8% / CEO.

## 8. Reference case: Azarpakhsh

| Item | Value (from corpus) |
|---|---|
| Contract | AR-CNT-1402-118, signed 12 Esfand 1402, 2,180M toman (hardware 720, web + Windows development 1,260, deployment and training 200) |
| Billing | Advance 654 (30%); billed 940 by end of Shahrivar 1403; remaining 1,240 |
| Progress | 62% physical progress (end of Shahrivar 1403) |
| Schedule | Planned delivery 15 Mordad 1403; proposed revised delivery 20 Mehr 1403 |
| Root cause | RAID controller and server RAM mismatch with Windows client needs, plus delayed web reporting module |
| Sub-issues | AR-ISS-024/HW → Saeed Akbari + Farzaneh Javadi; AR-ISS-024/WIN → Roozbeh Mohseni; AR-ISS-024/LEG → Mahsa Jalali |
| Decisions requested from board | Hardware amendment up to 95M; extension to 20 Mehr without penalty; spare-part petty cash 40 → 65M (proposed, not approved) |
| Related RFP | AR-RFP-1403-07 reporting module: Dadeh Pardaz Shafagh 78.8 (selected) vs Novin Gozaresh Pars 75.2 |
| Open research gaps | (1) faulty-part detection from photographs; (2) evaluation of repair-knowledge retrieval quality |

This one case touches every bounded context and will be the main end-to-end scenario for demonstrations (demonstrated manually; the automated suite remains unit tests only).

## 9. Key use cases

| ID | Use case | Actor / node | Example |
|---|---|---|---|
| UC-01 | Register layers and nodes | Project team | Load 5 layers and 21 nodes from CSV |
| UC-02 | Ingest a document as a versioned KnowledgeItem | Node owner | AR-HW-012 (FA + EN) into `N-HW-REP` |
| UC-03 | Detect duplicates and overlaps | System | Contract split repeated in FIN-008/FIN-010/ISS-024/TRN-026 |
| UC-04 | Ask a node-scoped question | Any node user | “What is the response time for a priority 1 incident?” → 30 minutes (AR-SW-022) |
| UC-05 | Create and decompose an issue | Node owner | Azarpakhsh issue → HW, WIN, LEG sub-issues |
| UC-06 | Suggest executors | System | AR-ISS-024/WIN → Roozbeh Mohseni |
| UC-07 | Compute progress and priority | System | Progress of AR-ISS-024 from sub-issue states |
| UC-08 | Run cyclic processing | Node / trigger | Quarter close at `N-SW` |
| UC-09 | Pull latest accepted package | Upper node | `N-CEO` pulls from `N-HW` and `N-SW` |
| UC-10 | Generate RFP and evaluate proposals | Software deputy | AR-RFP-1403-07 with bids A and B |
| UC-11 | Judge an output | System | L0 Azarpakhsh summary scored against 18/20 |
| UC-12 | Detect research gaps, rank key issues | System | Two gaps from AR-TRN-026 |

## 10. Data-quality findings in the sample corpus

| # | Finding | Impact | Handling |
|---|---|---|---|
| D1 | 8 Persian files write document IDs with Persian digits (e.g. `AR-FIN-۰۰۸`): FIN-008, LEG-009, FIN-010, HR-011, HW-012, HW-013, HW-014, HW-015 | Exact-match retrieval of IDs and cross-references fails | Normalize digits to Latin in IDs at ingestion (phase 4) and add a unit test; files left unchanged as realistic noise |
| D2 | Windows programmer spelled “Roozbeh” (9 EN files) and “Rouzbeh” (11 EN files) | Executor matching and name search may split one person into two | Alias table in executor context; registry uses “Roozbeh Mohseni” |
| D3 | All 52 files are DOCX; no DOC or PDF samples | DOC and PDF ingestion metrics cannot be measured | Produce DOC and PDF exports of a subset in phase 4 (local conversion) |
| D4 | Same facts repeated across documents (contract split, RFP scores) | Duplicate detector could wrongly merge different documents | Treat as overlap, not duplicate; FA/EN pairs linked, not deduplicated |
| D5 | Documents contain proposals quoted inside approved documents (e.g. penalty waiver) | RAG may present a proposal as an approved fact | Trap questions in the evaluation set; judge criterion “no unsupported claim” |

## 11. Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Small local models handle Persian poorly (embedding and generation) | High | High | Benchmark bilingual candidates in phase 2; keep EN as fallback language for evaluation |
| R2 | LLM judge is unreliable or biased toward its own outputs | Medium | High | Human-reviewed calibration sample; judge model distinct from generator if hardware allows |
| R3 | Hardware limits (RAM/GPU) restrict model size and speed | Medium | Medium | Quantized models; measure latency in phase 2 |
| R4 | Scope creep across 16 phases | Medium | High | Fixed outputs per phase (GitHub issues #1–#16); spec section 4.2 as hard boundary |
| R5 | Only one formal issue file in the corpus | Medium | Medium | Derive additional synthetic issues from AR-TRN-026 challenges in phase 7 |
| R6 | Unit-test-only policy hides integration defects | Medium | Medium | Ports with contract tests on fakes; manual demonstration of the Azarpakhsh scenario |

## 12. Open questions for the supervisor

| # | Question |
|---|---|
| Q1 | Is the fictional ArmanRayan domain (26 bilingual documents) accepted as the case study, or is a real organizational dataset expected? |
| Q2 | Should the system answer in both Persian and English, or is Persian the primary evaluation language? |
| Q3 | Layer 4 (knowledge library) is a repository, not a reporting layer. Accept modeling it as an L4 node with parent `N-CEO` and an exemption from the “parent = layer − 1” rule? |
| Q4 | Are the initial metric targets in `evaluation-baseline.md` acceptable (Recall@5 ≥ 0.80, citation correctness ≥ 0.90, judge 18/20, ≥ 80% unit-test coverage)? |
| Q5 | Is 18/20 required for all important outputs or only for L0/L1 packages? |
| Q6 | Is a manual (non-automated) demonstration of the Azarpakhsh end-to-end scenario acceptable given the unit-test-only rule? |
| Q7 | Should DOC/PDF samples be derived from the corpus, or must they be independent documents? |
| Q8 | What hardware is available for local models (RAM, GPU), which bounds model choice in phase 2? |

## 13. Phase-1 task completion

| Phase-1 task (spec 21) | Result | Evidence |
|---|---|---|
| Define goals and study scope | Done | Sections 2–4 |
| Create shared DDD vocabulary | Done (initial, 98 terms) | `glossary.md`, `bounded-contexts-draft.md` |
| Collect initial sample documents | Done (52 DOCX + manifest) | `corpus/`, section 6 |
| Initial identification of layers and nodes | Done (5 layers, 21 nodes) | Section 7, `data/registry/` |
| Define initial evaluation metrics with the supervisor | Drafted; supervisor review pending | `evaluation-baseline.md` |
| Define unit-test approach | Done | `unit-test-policy.md` |

## 14. Next step — phase 2

Phase 2 (offline models and technical baseline): survey candidate small local Embedding, LLM and LVM models with Persian support; set up local execution; run sample prompts on corpus questions; record performance limits; define the model registry structure. Inputs from phase 1: glossary terms for model/prompt management, the evaluation baseline (MP-01..MP-08), and supervisor answers to Q2, Q4 and Q8.
