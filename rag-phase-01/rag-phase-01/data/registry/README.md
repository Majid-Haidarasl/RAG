# Layer and Node Registry (Phase 1)

| File | Purpose |
|---|---|
| `layer-registry.template.csv` | Empty template: header only |
| `layer-registry.sample.csv` | ArmanRayan layers L0–L4 (5 rows) |
| `node-registry.template.csv` | Empty template: header only |
| `node-registry.sample.csv` | ArmanRayan nodes (21 rows) |

Encoding UTF-8, comma-separated, first row is the header. Multi-value fields (`source_docs`) use `;`.

## Layer registry columns (spec 6.1, 10.1)

| Column | Meaning |
|---|---|
| `layer_index` | 0 = top. Value object `LayerIndex` |
| `layer_code` | `L0`…`L4` |
| `layer_name_en`, `layer_name_fa` | Bilingual layer name |
| `layer_role` | Role of the layer in the organization |
| `knowledge_needed_from_children` | What this layer requires from the layer below |
| `default_detail_level_received` | `executive`, `managerial`, `technical_summary`, `detailed_technical` |
| `required_transfer_format` | Expected TransferPackage format |
| `min_judge_score` | Minimum LLM-judge score out of 20 for accepted packages (initial: 18) |
| `max_package_words` | Initial length limit of a package sent to this layer |
| `source_citation_level` | Required citation granularity |
| `default_confidentiality` | Default visibility class |
| `notes` | Free text with source document |

## Node registry columns (spec 6.1)

| Column | Meaning |
|---|---|
| `node_id` | Stable `NodeIdentifier` (`N-<DEPUTY>-<UNIT>`) |
| `node_name_en`, `node_name_fa` | Names as in AR-ORG-002 and the manifest |
| `node_type` | `board`, `parent_organization`, `deputy`, `unit`, `team`, `knowledge_repository` |
| `layer_index` | Layer membership (exactly one) |
| `parent_node_id` | Reporting parent; empty only for the root |
| `head_or_key_contact` | Head or named key contact from the corpus |
| `activity_domain` | What the node is responsible for |
| `cost_center` | Code from AR-FIN-010 |
| `headcount` | Only where the corpus states it |
| `reporting_rule` | Upward reporting obligation |
| `transfer_detail_level_to_parent` | Detail level of packages sent to the parent |
| `transfer_format` | Package format |
| `confidentiality` | `restricted`, `internal`, or `per item` |
| `internal_structure_tracked` | `true` if child nodes are modeled |
| `is_leaf` | `true` if internal structure is outside the model (spec 6.2) |
| `source_docs` | Corpus documents that describe the node |
| `notes` | Aliases, exceptions |

## Validation rules (to be unit-tested in phase 6)

1. `node_id` unique; exactly one root (`N-BRD`).
2. Parent exists; no cycles.
3. `layer_index(parent) = layer_index(child) − 1`, except `knowledge_repository` nodes (open question Q3).
4. A leaf node has no children.
5. Technology names (Django, React, …) are never node names.
