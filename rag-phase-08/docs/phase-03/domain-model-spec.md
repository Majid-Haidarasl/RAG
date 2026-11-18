# Phase 3 — Domain Model Specification

Status: v1.0. Date: 10 November 2026 (19 Aban 1405).
Ubiquitous language: `docs/phase-01/glossary.md`. Architecture: `ddd-architecture.md`. Map: `context-map.md`.

Invariants are written in plain language first, then implemented on the aggregate listed. Every invariant that is already in code has at least one unit test (see `unit-test-plan.md`).

## 0. Shared kernel

Types that have **one meaning** in every context:

| Type | Kind | Rule |
|---|---|---|
| `NodeIdentifier` | VO | `N-` + uppercase alphanumerics and hyphens (`N-BRD`, `N-SW-WEB`) |
| `LayerIndex` | VO | Integer 0–9 (ArmanRayan uses 0–4); `L0` is the top; parent layer is child − 1 except the repository exemption |
| `DocumentId` | VO | `AR-…` with Latin digits after normalization |
| `IssueId` | VO | `AR-ISS-NNN` or `AR-ISS-NNN/SUFFIX` |
| `ExecutorId` | VO | `EX-…` |
| `ProjectId` | VO | `PRJ-…` (e.g. `PRJ-AZP-118`) |
| `RfpId` | VO | `AR-RFP-YYYY-NN` |
| `KnowledgeItemId` | VO | Usually equal to the document id |
| `LanguageCode` | VO | `fa` or `en` |
| `Confidentiality` | VO | `restricted`, `internal`, `per_item`, `public` |
| `DomainEvent`, `DomainError`, `InvariantError` | support | See architecture §6 |
| Numeral helpers, `FactValidator` port | support | `fact-validator-design.md` |

No shared aggregate lives here.

---

## 1. Organizational Hierarchy (`hierarchy`)

**Aggregate: `Organization`** (the node tree). `Node` is an entity inside it. A standalone Node aggregate would not be able to protect uniqueness, cycles or adjacency in one transaction; the ArmanRayan tree has 21 nodes, so one boundary is the right size.

**Aggregate: layers** are registered on the same `Organization` for now (`register_layer`). A later split into `LayerRegistry` is unnecessary until layers are edited independently of nodes.

| Building block | Name | Notes |
|---|---|---|
| Entity | `Node` | Identity `NodeIdentifier`; bilingual name; `NodeType`; `LayerIndex`; `parent_id`; `is_leaf`; optional capabilities, cost centre, confidentiality |
| Entity | `Layer` | Identity `LayerIndex`; bilingual name; default detail level; optional judge threshold and word limit |
| VO | `NodeType` | `board`, `parent_organization`, `deputy`, `unit`, `team`, `knowledge_repository` |
| Events | `NodeRegistered`, `NodeMarkedAsLeaf` | |
| Repository port | `OrganizationRepository` | `get` / `save` / `exists` |

Invariants:

1. Node ids are unique; there is exactly one root, and only a `board` node may have no parent (`N-BRD`).
2. The parent exists in the tree; a node cannot be its own parent; a new link must not create a cycle.
3. `layer(parent) = layer(child) − 1`, **except** `knowledge_repository` nodes (Q3 exemption: `N-LIB` → `N-CEO`).
4. Parent and child may not share a layer.
5. A leaf node has no children.
6. A technology name (`Django`, `React`, `Laravel`, `Node.js`, `Flutter`, `C#/.NET`, …) cannot be a node name; those values are capability tags (AR-ORG-002 s.6).
7. Node type and layer are consistent: board@L0, parent_organization@L1, deputy@L2, unit or team@L3, knowledge_repository@L4.
8. A node has non-empty bilingual names.

Application: `RegisterHierarchyService` (UC-01). Infrastructure: `InMemoryOrganizationRepository`.

---

## 2. Knowledge Management (`knowledge`)

**Aggregate: `KnowledgeItem`.** Members: `KnowledgeVersion` → `KnowledgeChunk`.

| Building block | Name | Notes |
|---|---|---|
| Root | `KnowledgeItem` | One item per document id; owning node; confidentiality; scope |
| Entity | `KnowledgeVersion` | `(VersionTag, LanguageCode)`; status active/inactive |
| Entity | `KnowledgeChunk` | `chunk_id`, order, text, heading path, section, content hash |
| VO | `VersionTag` | `major.minor` |
| VO | `KnowledgeScope` | subject domain + confidentiality + usage |
| VO | `SourceReference` | document, version, section/heading/chunk/page |
| VO / service output | `Citation` | Used by RAG, Transfer and Models; same meaning everywhere |
| Domain service | `DuplicateDetector` | exact / overlap / cross-language pair / distinct |
| Events | `KnowledgeItemRegistered`, `KnowledgeVersionActivated` | `DuplicateDetected` will be emitted by the service in a later phase |
| Ports | `KnowledgeItemRepository`, `DocumentParserPort`, `VectorStorePort` | Parsers and the index are stubs for later phases |

Invariants:

1. A KnowledgeItem has an owning node, a confidentiality class and a non-empty subject domain.
2. A version has at least one chunk; chunk ids are unique; chunks are stored in non-decreasing order and keep heading path / section.
3. Adding a version with the same language deactivates the previous active version of that language; the old version is kept.
4. FA and EN editions may share a `VersionTag`; they are a cross-language pair, not a duplicate.
5. Identical chunk-hash sets → exact duplicate. A proper subset of shared hashes → overlap (the Azarpakhsh contract split across FIN-008, FIN-010, ISS-024, TRN-026).
6. Chunk content hash is SHA-256 of the UTF-8 text (normalization beyond digits is a Phase 4/5 concern).

---

## 3. RAG Core (`rag`)

**Aggregate: `RetrievalSession`** (one question). Short-lived.

| Building block | Name | Notes |
|---|---|---|
| VO | `RetrievalQuery` | text, `node_scope`, language, `top_k` ≥ 1 |
| VO | `SimilarityScore` | real number in [0, 1] |
| Entity (inside session) | `RetrievedChunk` | includes an `allowed` flag for the node boundary |
| VO | `Answer` | `grounded` (must have citations) or `abstained` |
| Events | `AnswerGenerated`, `AnswerAbstained` | |
| Repository port | `RetrievalSessionRepository` | optional persistence later |

Invariants:

1. Query text is non-empty.
2. Chunks the node is not allowed to see are dropped before answering (`allowed=False`).
3. A grounded answer has at least one `Citation`; otherwise the session must abstain.
4. The session cannot record hits after it has produced an answer.

Generation goes through `LlmPort`; embeddings through `EmbeddingPort`. After generation, Phase 8 will run `FactValidator` before `ground()` is accepted.

---

## 4. Issue Management (`issues`)

**Aggregate: `Issue`.** `SubIssue` is an entity. **Supporting aggregate: `ProjectRecord`.**

| Building block | Name | Notes |
|---|---|---|
| VO | `IssueStatus` | new, analysing, knowledge_identified, executor_identified, solution_proposed, in_progress, awaiting_decision, resolved, unresolved, archived |
| VO | `ProgressPercentage` | 0–100 |
| VO | `PriorityScore` | non-negative; formula below |
| Events | `IssueCreated`, `IssueDecomposed` | `ResearchGapDetected` in a later phase |
| Ports | `IssueRepository`, `ProjectRecordRepository` | |

Invariants:

1. An issue has a non-empty title, a root `IssueId` (not a `/SUFFIX` id) and an owning node.
2. A sub-issue id must be a child of this root (`AR-ISS-024/WIN` of `AR-ISS-024`); positions are ≥ 1 and unique; adding a sub-issue emits `IssueDecomposed`.
3. Progress is always computed through the root: resolved/archived → 100; otherwise the mean of sub-issue progress if any exist, else the optional explicit value, else 0. The value is always in [0, 100].
4. Priority is deterministic: `3 * urgency + 2 * risk + dependents` (each input in 0–10). Ranking is a stable sort by descending score, then `IssueId`.
5. A project record has a title, an owning node and optional related issue ids.

The 62% figure in AR-ISS-024 is *reported* physical progress of the project, not necessarily this computed issue progress (glossary term 55). Tests use the computed rule; they do not claim that 62% is the mean of the three sub-issues.

---

## 5. Executor Management (`executors`)

**Aggregate: `Executor`** (a person / profile, not a node).

| Building block | Name | Notes |
|---|---|---|
| VO | `ExpertiseTag` | lower-cased non-empty |
| VO | `ReferralCapacity` | weekly hours 0–60 |
| Domain service | `suggest_executors` | filters by allowed referral domain |
| Function | `canonical_person_name` | alias table, finding D2 |

Invariants:

1. An executor has a display name (canonicalized), a home node, a capacity and a list of allowed referral domains.
2. A candidate whose allowed domains do not include the issue domain is excluded (policy item 11). Example: Roozbeh Mohseni may handle “warehouse desktop client”; Saeed Akbari may not.
3. `Rouzbeh Mohseni` and `Roozbeh Mohseni` are the same person.

---

## 6. IKE (`ike`)

**Aggregate: `IkeGraph`** (one per node). Members: `IkeRelation`.

| Building block | Name | Notes |
|---|---|---|
| VO | `RelationType` | `relates_to`, `can_handle`, `evidence_for`, `knowledge_lack` |
| VO | `RelationConfidence` | [0, 1] |
| Events | `RelationCreated`, `KnowledgeLackFlagged` | |

Invariants:

1. Endpoints are required and not reflexive.
2. `(source, target, type)` is unique inside the graph.
3. The graph does not embed Issue / Knowledge / Executor aggregates (ACL).

Example: `AR-ISS-024/WIN --relates_to--> AR-SW-019`; `EX-ROOZBEH-MOHSENI --can_handle--> AR-ISS-024/WIN`.

---

## 7. Knowledge Transfer (`transfer`)

**Aggregates: `TransferPackage`, `TransferRuleSet`.**

| Building block | Name | Notes |
|---|---|---|
| VO | `TransferDetailLevel` | executive, managerial, technical_summary, detailed_technical |
| VO | `TransferTrigger` | e.g. quarter close |
| VO | `PackageStatus` | draft, accepted, rejected |
| Events | `CycleCompleted`, `PackageAccepted`, `PackageRejected` | |
| Infrastructure | `package_to_csv` / `package_from_csv` | UTF-8 CSV, Persian text preserved |

Invariants:

1. Source and target nodes differ.
2. A package is assembled against a `TransferRuleSet`. For L0 the default required fields are `risks`, `decisions_requested` and `source_references`, and at least one `Citation` is required (policy item 12, AR-TRN-026).
3. An optional `max_words` on the rule is enforced.
4. Only a draft can be accepted or rejected; the latest accepted package is what an upper layer pulls (UC-09; repository method reserved).

---

## 8. Evaluation & Judging (`judging`)

**Aggregate: `JudgeEvaluation`.**

| Building block | Name | Notes |
|---|---|---|
| VO | `JudgeScore` | 0..`out_of` (default 20) |
| VO | `JudgeThreshold` | default minimum 18 |
| VO | `JudgeRubric` | named; carries a threshold |
| VO | `Verdict` | pass / fail |
| Port | `JudgePort` | returns raw JSON text |
| Event | `JudgeScoreBelowThreshold` | |

Invariants:

1. `17/20` fails; `18/20` passes (policy item 13).
2. Malformed or schemaless JSON raises `JudgeParseError` (not a score of 0).
3. The open host interface used by RAG, Transfer and RFP is `JudgePort`, not a direct LLM call.

---

## 9. RFP & Proposal (`rfp`)

**Aggregate: `Rfp`.** Members: `Proposal`.

| Building block | Name | Notes |
|---|---|---|
| VO | `CriterionWeight` | name + positive weight; weights sum to 1 or 100 |
| VO | `WeightedScore` | one decimal place (published scores are 78.8 and 75.2) |
| Function | `compute_weighted_score` | Σ score × weight |
| Events | `RfpPublished`, `ProposalEvaluated` | |

Invariants:

1. An RFP without criteria is rejected (policy item 15).
2. Technical 60% + financial 40% applied to the reconstructed component scores 82/74 (Dadeh Pardaz Shafagh) and 76/74 (Novin Gozaresh Pars) yields **78.8** and **75.2**. The component pair is reconstructed from the published totals because the exact cell values of AR-RFP-025 were not copied into this phase; this is called out for the supervisor.

---

## 10. Model & Prompt Management (`models`)

**Aggregates: `ModelRegistryEntry`, `PromptTemplate`** (`PromptVersion` is an entity).

| Building block | Name | Notes |
|---|---|---|
| VO | `TaskType`, `ModelRole`, `OutputSchema` | |
| Domain service | `PromptAssembler` | `string.Template` substitution; citations injected |
| Ports | `EmbeddingPort`, `LlmPort`, `LvmPort`, `PromptRegistry`, `ModelRegistryPort` | |
| Event | `PromptVersionPublished` | |
| Default data | `PHASE2_BASELINE` | bge-m3 dim 1024; qwen3:8b; qwen2.5vl:3b |

Invariants:

1. An embedding entry declares `embedding_dim`.
2. Prompt versions are unique per template; assembly fails on a missing variable.
3. A template that includes `$citations` receives a citation list (policy item 14).

---

## 11. Repository convention

Every aggregate has a typing `Protocol` in `domain/`. Phase 3 implements in-memory adapters where a test needed one (`Organization`, `KnowledgeItem`, `Issue`, model and prompt registries). Contract tests that compare an in-memory fake with a CSV adapter belong to Phase 6 (policy item 18).
