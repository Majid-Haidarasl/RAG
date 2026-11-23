# eval/results

`scripts/run_eval_check.py` (Phase 14) writes its outputs here. They are not committed; this README is.

| File | What it holds |
|---|---|
| `phase-14-check-<UTC>.json` | Full run: checks, gold-set problems, offline and live retrieval per variant, the 42 judge calibration cases with every verdict, Q&A answers per prompt, required-id runs, the measured winner per kind and timings |
| `updated-metrics-<UTC>.md` | The same numbers as short Markdown tables, in the same layout as `docs/phase-14/updated-metrics.md` |

`<UTC>` is the run time in UTC (`20261124T101500Z`). The newest file pair is the last run. Old files can be deleted.

To compare one run with another, read the `retrieval_offline`, `live.retrieval`, `live.qa.runs`,
`live.judge.reports` and `live.ids.summary` sections, or the tables in the Markdown file.
