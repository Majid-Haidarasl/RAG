# data/judge — Phase 10 judge fixtures

* `calibration-set.json` — 14 hand-labelled outputs (8 good, 6 bad) with short source excerpts quoted from the corpus. `gold` is the decision of a careful reviewer with the 18/20 rubric. The case tagged `rule_blind_spot` (two correct numbers in swapped places) is a known limit of the rule judge; only the LLM judge can catch it.
* `parser-cases.json` — raw judge replies (plain JSON, code fences, think blocks, single quotes, unquoted keys, `key: value` lines, Persian digits, cut-off replies, malformed replies) and the expected parse result.

Labels such as `AR-SW-022 §4` in the calibration set are fixture labels, not Phase 8 chunk numbers.
