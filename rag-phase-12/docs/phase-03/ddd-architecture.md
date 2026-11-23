# Phase 3 — DDD Architecture

Status: v1.0 for supervisor review. Date: 10 November 2026 (19 Aban 1405).
Project: offline hierarchical RAG core · case study ArmanRayan IT.
Inputs: Phase 1 bounded-contexts draft, glossary, unit-test policy, layer/node registry; Phase 2 model-usage guide and model registry 0.3.0.

This document fixes the software architecture of the core: layers, dependency rules, and the ports that isolate local models, parsers and the vector store from the domain. Tactical models live in `domain-model-spec.md`. Context relationships live in `context-map.md`.

## 1. Style

The core is a **hexagonal (ports and adapters)** design organized as four layers, with **ten bounded contexts** plus a small shared kernel. It is a software core, not a product UI or a network service (assumption A3, spec 4.2).

Everything that talks to the outside world — Ollama, the filesystem, a future CSV/SQLite store, a future CLI — sits behind a port. Domain code never imports an HTTP client, a parser library or a model name.

## 2. Layers

```
┌─────────────────────────────────────────────────────────────┐
│ interfaces     CLI / future UI adapters (none in Phase 3)   │
└────────────────────────────┬────────────────────────────────┘
                             │ depends on
┌────────────────────────────▼────────────────────────────────┐
│ application    use-case services (UC-01 … UC-12)            │
│                orchestrate aggregates, domain services,     │
│                repositories and model ports                 │
└────────────────────────────┬────────────────────────────────┘
                             │ depends on
┌────────────────────────────▼────────────────────────────────┐
│ domain         aggregates, entities, value objects,         │
│                domain events, domain services,              │
│                repository and model *ports* (Protocols)     │
└─────────────────────────────────────────────────────────────┘
                             ▲ implemented by
┌────────────────────────────┴────────────────────────────────┐
│ infrastructure   in-memory repositories (this phase),       │
│                  future: Ollama adapters, DOC/DOCX/PDF      │
│                  parsers, local vector index, CSV/DB        │
└─────────────────────────────────────────────────────────────┘
```

| Layer | May know about | Must not know about |
|---|---|---|
| Domain | Shared kernel; its own ubiquitous language | Ollama, HTTP, paths, pytest, JSON files, CSV layouts, GPU |
| Application | Domain of its context; ports; other contexts only through published types or an ACL | Concrete adapters, framework containers |
| Infrastructure | Domain ports it implements; local OS and localhost Ollama | Other contexts' internals; the public internet |
| Interfaces | Application services | Domain internals, adapters |

**Dependency rule.** Source-code dependencies point inward: `interfaces → application → domain ← infrastructure`. A domain module that imports `rag_core.*.infrastructure` or `ollama` is a defect. Unit tests enforce behaviour, not import lints, but reviewers should treat such an import as a failed review.

## 3. Package layout

```
src/rag_core/
  shared_kernel/          # identifiers, LayerIndex, language, numerals, events, errors
  <context>/
    domain/               # model, ports, repository Protocols, domain services
    application/          # use-case services (thin in this phase)
    infrastructure/       # in-memory adapters now; Ollama/parsers later
```

Context package names follow the Phase 1 codes:

| Code | Context |
|---|---|
| `hierarchy` | Organizational Hierarchy |
| `knowledge` | Knowledge Management |
| `rag` | RAG Core |
| `issues` | Issue Management |
| `executors` | Executor Management |
| `ike` | Issue–Knowledge–Executor |
| `transfer` | Knowledge Transfer |
| `judging` | Evaluation & Judging |
| `rfp` | RFP & Proposal |
| `models` | Model & Prompt Management |

Python 3.12+, package name `rag_core`, no runtime dependencies. Dev extra: `pytest`, `pytest-cov`.

## 4. Ports and adapters

### 4.1 Model ports (owned by Model & Prompt Management)

These match the Phase 2 contract (`model-usage-guide.md` section 6):

| Port | Method | Production adapter (later) | Test double |
|---|---|---|---|
| `EmbeddingPort` | `embed(texts) -> list[vector]` | `OllamaEmbeddingAdapter` → `POST localhost:11434/api/embed`, model `bge-m3:latest`, `num_ctx` 8192, `keep_alive` 30m | `FakeEmbeddingModel` (hash-derived, fixed dim) |
| `LlmPort` | `complete(prompt_id, version, variables, schema?, think?) -> LlmResult` | `OllamaLlmAdapter` → `/api/chat`, model `qwen3:8b`. Defaults: `think=false`, `temperature=0.2`, `num_ctx=8192`, JSON schema `format` for structured tasks. Think-mode retry only for the FA-18 pattern (abstention despite a high-scoring hit). `strip_think()` stays in the adapter. Decomposition never uses think-on. | `FakeLlm` (scripted by prompt id) |
| `LvmPort` | `read(image, task_prompt) -> LvmResult` | `OllamaLvmAdapter`, model `qwen2.5vl:3b`, loaded on demand and unloaded (`keep_alive: 0`). Do not co-reside with embedding+LLM on a 12 GB GPU. | `FakeLvm` |
| `PromptRegistry` | `get` / `save` | YAML/JSON registry (Phase 2 `config/prompt-registry.json` is the seed) | `InMemoryPromptRegistry` |
| `ModelRegistryPort` | `get` / `list_baseline` | YAML registry 0.3.0 | `InMemoryModelRegistry` seeded with the three selected models |

Domain and application code refer to models by registry id (`emb-bge-m3`, `llm-qwen3-8b`, `lvm-qwen2.5vl-3b`), never by a hard-coded Ollama name. The adapter reads the name from the registry.

### 4.2 Other ports

| Port | Owner | Purpose | When implemented |
|---|---|---|---|
| `DocumentParserPort` | Knowledge | Parse a local DOC, DOCX or PDF. No network. | Phase 4 (ingestion) |
| `VectorStorePort` | Knowledge / RAG | Upsert, filtered search, delete of chunk vectors | Ingestion / retrieval phases |
| `JudgePort` | Judging | Score an output against a rubric; returns raw JSON | Later; `FakeJudge` is already in `tests/fakes` |
| `FactValidator` | Shared kernel (contract); Knowledge holds source text | Verify names, IDs and numbers against sources | Design now; implementation Phase 8 |
| `*Repository` | Each context | Persistence of aggregates | In-memory now; CSV/local DB from Phase 6 onward |

### 4.3 Offline-only rules

1. Production adapters may call only `http://127.0.0.1:11434` (or the configured localhost URL). They must not set `OLLAMA_HOST=0.0.0.0`.
2. No adapter may open a public-internet socket. Unit tests that open a socket are out of policy and must fail.
3. File access in tests goes through pytest's `tmp_path`. Unit tests do not read `corpus/`.
4. Model quality is measured by the Phase 2 / evaluation-baseline suites, not by this unit-test suite.

## 5. Application services

Phase 3 ships one thin service, `RegisterHierarchyService` (UC-01), to show the pattern: load the aggregate from a repository, call a domain method, save. The remaining use cases get application services in the phases that implement them (ingestion, retrieval, issues, transfer, RFP). Until then, invariants are exercised directly on aggregates.

## 6. Events and errors

- `DomainEvent` is a frozen record (`name`, `payload`, `occurred_at`). An outbox or message bus is out of scope; aggregates append events for the application layer to observe.
- `DomainError` / `InvariantError` / `NotFoundError` are the only exception types the domain raises. Interfaces map them later.

## 7. What this phase does not build

- Ollama adapters, prompt execution, VRAM management (specified, not coded).
- DOC/DOCX/PDF parsers and the vector index (Phase 4+).
- Full `FactValidator` implementation (Phase 8). Numeral and document-id normalization is already in the shared kernel.
- CSV/SQLite persistent repositories (a TransferPackage CSV round-trip helper is included as a pure function).
- Any CLI, API or UI.

## 8. Consistency with earlier phases

| Decision | Source | Where it lands |
|---|---|---|
| Ten contexts, English terms as class names | glossary, contexts draft | package and type names |
| Unit tests only; deterministic fakes | unit-test-policy.md | `tests/fakes`, no I/O |
| bge-m3, qwen3:8b, qwen2.5vl:3b on demand | model-registry.yaml 0.3.0 | `PHASE2_BASELINE` and model ports |
| Think off by default; schema-mode decomposition | model-usage-guide.md | adapter contract in §4.1 |
| Names, IDs, numbers checked in code against the source | Phase 2 conditions | `fact-validator-design.md` |
| L4 library may report to `N-CEO` (Q3, assumed yes) | domain-discovery Q3, node registry | `Organization` parent-child rule |
