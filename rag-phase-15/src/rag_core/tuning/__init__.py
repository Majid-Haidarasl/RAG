"""Phase 14 bounded context: prompt testing, retrieval tuning and sample evaluation.

* ``domain``         — gold Q&A items and their validation, ranking / agreement /
                       latency metrics, variant selection, required-id checks;
* ``application``    — comparisons of retrieval variants, judge variants and
                       required-id prompt variants (ports are plain callables);
* ``infrastructure`` — JSONL dataset, ``config/eval.yaml``, anti-corruption
                       layers to the rag, qa, judging and rfp contexts.
"""
