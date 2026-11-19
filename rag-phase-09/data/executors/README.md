# Executor registry (Phase 9)

| File | Content |
|---|---|
| `executor-registry.json` | The 15 named executors of AR-EXE-023 (schema `executor-registry/1.0`) with profile, expertise metadata, knowledge documents and referral capacity. |

Executor fields:

* identity: `id` (`EX-<FIRST>-<LAST>`, derived from `name_en`), `name_en`, `name_fa`, `aliases` (spellings used elsewhere, e.g. `Rouzbeh Mohseni` in the issue registry);
* role: `role_en`, `role_fa`, `home_node` (a Phase 6 team node, layer 3);
* expertise metadata: `specialty`, `allowed_referral_domains` (+ `_fa`), `expertise` (tags), `knowledge_documents` (catalog ids the executor holds);
* responsibilities: `outputs`, `authority_limits`;
* `capacity_hours_per_week`: published referral hours per week, or `null` when AR-EXE-023 says capacity is allocated through unit planning (neither zero nor unlimited);
* `profile_version`, `source`.

Pay, salary and other confidential HR data are deliberately not stored; the validator warns if a pay-like key appears.

Validation rules (`ExecutorRegistryValidator`): required fields, id format, unique ids, id derived from the English name, home node exists and is a team (layer 3), knowledge documents exist in the corpus catalog, capacity in 0–60 h/week; warnings for unpublished capacity and confidential keys.
