# Issue registry (Phase 7)

| File | Content |
|---|---|
| `issue-registry.json` | Seed issues with metadata and sub-issues. AR-ISS-024 (Azarpakhsh) comes from the corpus; AR-ISS-031…036 are synthetic seeds derived from corpus facts (FIN-008, TRN-026, EXE-023, RFP-025, ISS-024 §9) so comparison has something to compare against. |
| `new-issue-samples.json` | Incoming issues with expected comparison labels (duplicate / related / new), used by `scripts/run_issue_check.py`. |

Issue fields:

* identity and text: `id`, `title_en`, `title_fa`, `description_en`, `description_fa`, `customer`;
* nodes: `reporter_node`, `owner_node`, `affected_nodes` (Phase 6 node ids);
* links: `related_documents` (catalog ids), `contract_ref`, `duplicate_of`, `related_issues`;
* classification: `category`, `severity`, `priority` (P1–P4, AR-SW-022);
* state: `status`, `resolution`;
* dates: `opened_on`, `due_on` (ISO; Jalali dates in `dates_jalali`);
* scoring and decisions: `progress_percent`, `decision_amount_mtoman`, `urgency`, `risk`, `dependents`;
* `tags`;
* `sub_issues`.

Sub-issue fields:

* `id` (`<parent>/<CODE>`), `position`, `title_en`, `title_fa`, `scope`;
* `owner_node`, `supporting_nodes`, `related_documents`, `executors`, `acceptance_output`;
* `status`, `blocked_reason`, `depends_on` (sibling codes), `reserved_decision`.

The validation rules are listed in `docs/phase-07/issue-model.md` §7.
