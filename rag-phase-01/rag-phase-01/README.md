# Offline Hierarchical RAG Core — Phase 1: Project Kickoff & Domain Discovery

Student project: an offline, DDD-based hierarchical RAG core for organizational knowledge management, issue management and managerial knowledge transfer, using small local Embedding/LLM/LVM models, DOC/DOCX/PDF ingestion and unit tests only. This package holds the outputs of **phase 1 of 16**.

Case study: **ArmanRayan IT** — fictional Tehran company, ~85 staff, 5 layers, 21 nodes, 26 bilingual documents.

## Outputs

| Path | Content |
|---|---|
| `docs/phase-01/domain-discovery.md` | Goals, scope, assumptions, stakeholders, document inventory, layers and nodes, Azarpakhsh case, use cases, data-quality findings, risks, supervisor questions |
| `docs/phase-01/glossary.md` | Bilingual ubiquitous language: 98 terms (EN, FA, definition, context, ArmanRayan example) |
| `docs/phase-01/bounded-contexts-draft.md` | 10 bounded contexts, candidate aggregates, context map, use-case mapping |
| `docs/phase-01/evaluation-baseline.md` | 44 component metrics + 8 model/prompt metrics + judge rubric; initial targets pending supervisor review |
| `docs/phase-01/unit-test-policy.md` | Unit-test scope, pytest tooling, deterministic fakes, naming, coverage target |
| `data/registry/layer-registry.template.csv` | Layer registry header |
| `data/registry/layer-registry.sample.csv` | ArmanRayan L0–L4 |
| `data/registry/node-registry.template.csv` | Node registry header |
| `data/registry/node-registry.sample.csv` | 21 ArmanRayan nodes |
| `data/registry/README.md` | Column dictionary and validation rules |
| `corpus/README.md` | Corpus description and known data-quality issues |
| `corpus/fa/`, `corpus/en/`, `corpus/manifest.md` | 26 FA + 26 EN DOCX documents and manifest |
| `گزارش-فاز-۱.docx` | Persian completion report |

## Phase-1 checklist (GitHub issue #1)

- [x] `docs/phase-01/domain-discovery.md`
- [x] `docs/phase-01/glossary.md`
- [x] `docs/phase-01/bounded-contexts-draft.md`
- [x] `data/registry/layer-registry.template.csv`
- [x] `data/registry/node-registry.template.csv`
- [x] `docs/phase-01/evaluation-baseline.md`
- [x] `docs/phase-01/unit-test-policy.md`
- [x] `corpus/README.md`

Pending outside this package: supervisor review of metric targets and open questions Q1–Q8 (`domain-discovery.md` section 12).

## Next: phase 2

Offline models and technical baseline — candidate Embedding/LLM/LVM models with Persian support, local execution, sample prompts on corpus questions, model-registry structure.
