# Phase 1 — Bounded Contexts (Draft)

Status: draft 0.1 for supervisor review. The final context map, aggregates and invariants are fixed in **phase 3** (DDD architecture and core domain model). This draft only fixes names and responsibilities so phases 2–3 start from one vocabulary (see `glossary.md`).

Source: project specification section 5.1 (ten proposed contexts), 5.2 (entities), 5.3 (value objects), mapped onto the ArmanRayan IT corpus.

## 1. Context list

| # | Context | Code | Responsibility | Candidate aggregates (root → members) | Key value objects | Example domain events | Corpus evidence |
|---|---|---|---|---|---|---|---|
| 1 | Organizational Hierarchy | `hierarchy` | Layers, nodes, parent–child relations, activity domains, reporting rules, node boundary, leaf nodes | `Node`; `LayerRegistry` → `Layer` | `NodeIdentifier`, `LayerIndex` | `NodeRegistered`, `NodeMarkedAsLeaf` | AR-ORG-001, AR-ORG-002 |
| 2 | Knowledge Management | `knowledge` | KnowledgeItems, versions, chunks, metadata, source references, duplicates and overlaps, lifecycle | `KnowledgeItem` → `KnowledgeVersion` → `KnowledgeChunk` | `VersionTag`, `KnowledgeScope`, `MetadataRecord`, `SourceReference` | `KnowledgeItemRegistered`, `KnowledgeVersionActivated`, `DuplicateDetected` | all 26 documents; manifest |
| 3 | RAG Core | `rag` | Embedding, retrieval, ranking, context assembly, grounded generation, node-scoped Q&A | `RetrievalSession` (query → retrieved chunks → answer) | `RetrievalQuery`, `SimilarityScore` | `AnswerGenerated`, `AnswerAbstained` | ISS-024 retrieval cases (“Who handles the Windows problem?”) |
| 4 | Issue Management | `issues` | Issues, sub-issues, relative position, status, progress, priority, key issues, research gaps, project records | `Issue` → `SubIssue`; `ProjectRecord` | `ProgressPercentage`, `PriorityScore`, `IssueStatus` | `IssueCreated`, `IssueDecomposed`, `ResearchGapDetected` | AR-ISS-024, AR-TRN-026 |
| 5 | Executor Management | `executors` | Executor profiles, expertise tags, referral capacity, allowed referral domain, assignment suggestion | `Executor` | `ExpertiseTag`, `ReferralCapacity` | `ExecutorProfileUpdated` | AR-EXE-023, AR-HR-004..007 |
| 6 | Issue-Knowledge-Executor (IKE) | `ike` | Typed relations between issues, knowledge and executors; IKE as node knowledge | `IkeGraph` (per node) → `IkeRelation` | `RelationType`, `RelationConfidence` | `RelationCreated`, `KnowledgeLackFlagged` | AR-ISS-024 sub-issue table |
| 7 | Knowledge Transfer | `transfer` | Transfer rules per layer, cyclic processing, TransferPackage assembly, detail level, latest accepted package, CSV/DB storage | `TransferPackage`; `TransferRuleSet` (per layer) | `TransferDetailLevel`, `Trigger` | `CycleCompleted`, `PackageAccepted`, `PackageRejected` | AR-TRN-026 transfer matrix |
| 8 | Evaluation & Judging | `judging` | LLM-as-judge scoring against source, request, rule and rubric; thresholds; human-review flags | `JudgeEvaluation` | `JudgeRubric`, `JudgeScore`, `JudgeThreshold` | `JudgeScoreBelowThreshold` | — (spec section 16) |
| 9 | RFP & Proposal | `rfp` | RFP generation, proposal registration, criterion scoring, weighted score, feedback | `Rfp` → `Proposal` → `ProposalEvaluation`; `FeedbackReport` | `CriterionWeight`, `WeightedScore` | `RfpPublished`, `ProposalEvaluated` | AR-RFP-025 |
| 10 | Model & Prompt Management | `models` | Local model registry, prompt templates and versions, prompt assembly rules, prompt test records | `ModelRegistryEntry`; `PromptTemplate` → `PromptVersion` | `TaskType`, `OutputSchema` | `PromptVersionPublished` | — (spec section 8.2–8.3) |

## 2. Context map (initial)

```
                    ┌───────────────────────────┐
                    │ Organizational Hierarchy  │  (upstream: node IDs, layers, boundaries)
                    └─────────────┬─────────────┘
          ┌───────────────────────┼─────────────────────────┐
          ▼                       ▼                         ▼
 ┌─────────────────┐     ┌─────────────────┐       ┌─────────────────┐
 │ Knowledge Mgmt  │────▶│    RAG Core     │◀──────│ Model & Prompt  │
 └────────┬────────┘     └───────┬─────────┘       └────────┬────────┘
          │                      │                          │
          ▼                      ▼                          ▼
 ┌─────────────────┐     ┌─────────────────┐       ┌─────────────────┐
 │ Issue Mgmt      │────▶│ IKE Model       │◀──────│ Executor Mgmt   │
 └────────┬────────┘     └───────┬─────────┘       └─────────────────┘
          │                      │
          ▼                      ▼
 ┌─────────────────┐     ┌─────────────────┐       ┌─────────────────┐
 │ RFP & Proposal  │     │ Knowledge       │──────▶│ Evaluation &    │
 └────────┬────────┘     │ Transfer        │       │ Judging         │
          └─────────────▶└─────────────────┘       └─────────────────┘
```

Relationship notes:

- **Hierarchy is upstream of everything** (shared kernel: `NodeIdentifier`, `LayerIndex`). Every KnowledgeItem, Issue, Executor and TransferPackage carries a node ID.
- **RAG Core consumes Knowledge Management** through a read model of active chunks; it never edits KnowledgeItems. Generated answers that must become node knowledge are sent back as a new KnowledgeItem (spec 8.1 step 12).
- **IKE is a downstream integration context** that reads issues, knowledge and executors and owns only the relations.
- **Evaluation & Judging is a generic service** used by RAG Core, Knowledge Transfer and RFP & Proposal through one port (`JudgePort`).
- **Model & Prompt Management** exposes ports (`EmbeddingPort`, `LlmPort`, `LvmPort`, `PromptRegistry`). Unit tests replace them with deterministic fakes (`unit-test-policy.md`).

## 3. Use-case to context mapping (initial)

| Use case (from domain discovery) | Primary context | Supporting contexts |
|---|---|---|
| UC-01 Register the ArmanRayan layers and 21 nodes | Hierarchy | — |
| UC-02 Ingest a DOCX/DOC/PDF document as a versioned KnowledgeItem | Knowledge | Model & Prompt (LVM for layout) |
| UC-03 Detect duplicate/overlapping chunks (e.g., the Azarpakhsh contract split repeated in four documents) | Knowledge | RAG Core (embeddings) |
| UC-04 Answer a node-scoped question with citations or abstain | RAG Core | Knowledge, Hierarchy, Judging |
| UC-05 Create an issue with metadata and decompose it into sub-issues | Issues | RAG Core, IKE |
| UC-06 Suggest executors for a sub-issue | Executors | IKE |
| UC-07 Compute issue progress and priority | Issues | — |
| UC-08 Run cyclic processing and store the latest TransferPackage as CSV/DB | Transfer | Issues, IKE, Judging |
| UC-09 Deliver the latest accepted package to an upper layer | Transfer | Hierarchy |
| UC-10 Generate an RFP, register and evaluate proposals, generate feedback | RFP | Issues, Judging |
| UC-11 Score an output with the LLM judge against the 18/20 threshold | Judging | Model & Prompt |
| UC-12 Detect research gaps and rank key issues | Issues | IKE, Judging |

## 4. Open points for phase 3

1. Whether `Executor` and `Node` share a kernel (a team node is also an executor candidate).
2. Whether `ProjectRecord` belongs to Issue Management or to its own small context.
3. Where cross-language pairing (FA/EN files of the same document ID) is modeled: as two KnowledgeItems linked by a relation, or one KnowledgeItem with two language versions.
