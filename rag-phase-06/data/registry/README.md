# Layer, node and document-ownership registry (Phase 6)

Built from the Phase 1 samples (`layer-registry.sample.csv`, `node-registry.sample.csv`), AR-ORG-002 (structure), AR-TRN-026 §6 (inter-layer transfer matrix), AR-BRD-003 (Board approvals) and the ingestion catalog (document owners). UTF-8, comma-separated, multi-value fields use `;`.

| File | Rows | Content |
|---|---|---|
| `layer-registry.csv` | 5 | L0–L4 with Phase 1 columns plus transfer requirements |
| `node-registry.csv` | 21 | ArmanRayan nodes with Phase 1 columns plus `status`, `escalation_node_id` |
| `document-node-map.csv` | 26 documents | Document → node links with role `owner` (exactly one per document), `co_owner`, `described_in` |

New layer columns (transfer requirements):

| Column | Meaning |
|---|---|
| `transfer_direction` | `up` (to parent layer), `down` (L0 resolutions to L1), `peer` (L4 with L3: indexing, no upward summary) |
| `transfer_target` | Receiving layer code |
| `must_hand_over` | What the layer must hand over |
| `min_artefacts` | Minimum artefacts (`;`), validated: at least 2 |
| `approvals_required` | Approvals before the hand-over counts (`;`), validated: at least 1 |
| `required_feedback` | Feedback the receiver must return (AR-TRN-026 §6) |
| `transfer_sources` | Corpus documents behind the requirement |

New node columns: `status` = `active` or `retired`; `escalation_node_id` empty = escalate to parent.

Validate with `python scripts/run_hierarchy_check.py`. The rules are listed in `docs/phase-06/hierarchy-workflows.md`.
