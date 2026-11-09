#!/usr/bin/env python3
"""Embedding baseline (bge-m3): Recall@1/3/5, MRR per language mode, latency, dimension.

Modes:
  fa          FA questions  -> FA-only index
  en          EN questions  -> EN-only index
  cross_fa2en FA questions  -> EN-only index (cross-lingual)
  cross_en2fa EN questions  -> FA-only index (cross-lingual)
  mixed       all questions -> full bilingual index (hit if either language version ranks)
"""
import argparse
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from common import (DATA, DEFAULT_HOST, MODELS, Ollama, OllamaError, cosine, log, mean, pct,
                    rank_ids, read_jsonl, recall_at_k, reciprocal_rank, setup_utf8, write_json)

TARGETS = {"recall@5": 0.80, "mrr": 0.60}   # MP-01 / C-14 (Phase 1 evaluation-baseline.md)


def evaluate(qs, qvec, idx, rel_lang):
    rows = []
    for q in qs:
        ranked = rank_ids(qvec[q["qid"]], idx)
        ids = [r[0] for r in ranked]
        rel = set(q["relevant"]["fa"] + q["relevant"]["en"]) if rel_lang == "both" else set(q["relevant"][rel_lang])
        rows.append({"qid": q["qid"], "r1": recall_at_k(ids, rel, 1), "r3": recall_at_k(ids, rel, 3),
                     "r5": recall_at_k(ids, rel, 5), "rr": reciprocal_rank(ids, rel),
                     "top3": [(i, round(s, 4)) for i, s in ranked[:3]], "relevant": sorted(rel)})
    m = {"n": len(rows), "recall@1": mean([r["r1"] for r in rows]), "recall@3": mean([r["r3"] for r in rows]),
         "recall@5": mean([r["r5"] for r in rows]), "mrr": mean([r["rr"] for r in rows])}
    m["meets_MP-01"] = bool(m["recall@5"] is not None and m["recall@5"] >= TARGETS["recall@5"]
                            and m["mrr"] >= TARGETS["mrr"])
    m["failures_top1"] = [{"qid": r["qid"], "got": r["top3"][0][0], "expected": r["relevant"]}
                          for r in rows if r["r1"] == 0]
    return m, rows


def run(client: Ollama, out_dir: str, quick: bool = False) -> dict:
    model = MODELS["embedding"]
    chunks = read_jsonl(DATA / "chunks.jsonl")
    qs = read_jsonl(DATA / "gold_questions.jsonl")
    res = {"model": model, "status": "ok", "n_chunks": len(chunks), "n_questions": len(qs)}
    try:
        # cold call (includes model load)
        _, cold, _ = client.embed(model, ["warm-up / گرم‌کردن مدل"])
        res["cold_first_call_s"] = round(cold, 3)
        # batch embeddings
        cvecs, t_c, raw = client.embed(model, [c["text"] for c in chunks])
        qvecs, t_q, _ = client.embed(model, [q["question"] for q in qs])
        # second (warm) batch: the first batch in run 20261109-184242 cost 284 ms/chunk vs 13 ms single
        _, t_c2, _ = client.embed(model, [c["text"] for c in chunks])
    except OllamaError as e:
        log(f"embedding test failed: {e}")
        return {"model": model, "status": "error", "error": str(e)}
    if len(cvecs) != len(chunks) or len(qvecs) != len(qs):
        return {"model": model, "status": "error", "error": "embedding count mismatch"}
    res["embedding_dim"] = len(cvecs[0])
    res["batch_chunks_s"] = round(t_c, 3)
    res["batch_ms_per_chunk"] = round(1000 * t_c / len(chunks), 2)
    res["batch_ms_per_question"] = round(1000 * t_q / len(qs), 2)
    res["batch_warm_ms_per_chunk"] = round(1000 * t_c2 / len(chunks), 2)
    res["avg_chunk_chars"] = round(statistics.mean(len(c["text"]) for c in chunks))
    # single-text latency (warm)
    sample = [c["text"] for c in chunks if c["lang"] == "fa"][:5] + [c["text"] for c in chunks if c["lang"] == "en"][:5]
    if quick:
        sample = sample[:2] + sample[5:7]
    lat = []
    for t in sample:
        try:
            _, dt, _ = client.embed(model, [t])
            lat.append(1000 * dt)
        except OllamaError as e:
            log(f"single embed failed: {e}")
    res["single_text_latency_ms"] = {"n": len(lat), "mean": mean(lat), "p50": pct(lat, 50), "p95": pct(lat, 95)}

    cv = {c["chunk_id"]: v for c, v in zip(chunks, cvecs)}
    qv = {q["qid"]: v for q, v in zip(qs, qvecs)}
    idx = {lang: [(c["chunk_id"], cv[c["chunk_id"]]) for c in chunks if c["lang"] == lang] for lang in ("fa", "en")}
    idx_all = [(c["chunk_id"], cv[c["chunk_id"]]) for c in chunks]
    fa_q = [q for q in qs if q["lang"] == "fa"]
    en_q = [q for q in qs if q["lang"] == "en"]
    modes, details = {}, {}
    for name, qset, index, rel in (("fa", fa_q, idx["fa"], "fa"), ("en", en_q, idx["en"], "en"),
                                   ("cross_fa2en", fa_q, idx["en"], "en"), ("cross_en2fa", en_q, idx["fa"], "fa"),
                                   ("mixed", qs, idx_all, "both")):
        modes[name], details[name] = evaluate(qset, qv, index, rel)
    res["modes"] = modes
    # cross-lingual alignment: parallel FA/EN chunk similarity vs. non-parallel
    topics = sorted({c["topic"] for c in chunks})
    par = [cosine(cv[f"fa-{t}-c1"], cv[f"en-{t}-c1"]) for t in topics]
    non = [cosine(cv[f"fa-{a}-c1"], cv[f"en-{b}-c1"]) for a in topics for b in topics if a != b]
    res["parallel_pair_cosine"] = {"parallel_mean": mean(par), "non_parallel_mean": mean(non),
                                   "gap": round(mean(par) - mean(non), 4)}
    write_json(os.path.join(out_dir, "embedding_details.json"), details)
    log(f"embedding: dim={res['embedding_dim']} mixed R@5={modes['mixed']['recall@5']} MRR={modes['mixed']['mrr']}")
    return res


def main():
    setup_utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = a.out or str(DATA.parent / "results" / ("embed-" + time.strftime("%Y%m%d-%H%M%S")))
    os.makedirs(out, exist_ok=True)
    res = run(Ollama(a.host), out, a.quick)
    write_json(os.path.join(out, "embedding_results.json"), res)
    print(f"saved -> {out}")


if __name__ == "__main__":
    main()
