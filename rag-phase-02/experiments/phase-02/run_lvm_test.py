#!/usr/bin/env python3
"""LVM baseline (qwen2.5vl:3b): read an org chart, a FA/EN financial table and a scanned
Persian SLA page; score names/numbers against the expected answers; measure latency."""
import argparse
import base64
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from common import (DATA, DEFAULT_HOST, MODELS, Ollama, OllamaError, append_jsonl, extract_json,
                    fact_hits, load_prompts, log, mean, normalize, pct, render, setup_utf8, write_json)

OPTS = {"temperature": 0.1, "num_ctx": 8192, "num_predict": 1024, "seed": 42}
QUICK_TASKS = {"org-reporting", "table-qa"}


def numbers_in(text):
    return set(re.findall(r"\d+(?:\.\d+)?", normalize(text)))


def run(client: Ollama, out_dir: str, quick: bool = False) -> dict:
    model = MODELS["lvm"]
    p = load_prompts()["lvm.read"]
    with open(DATA / "images" / "images.json", encoding="utf-8") as f:
        spec = json.load(f)["images"]
    runs, errors = [], 0
    log(f"LVM test on {model} (quick={quick})")
    for img in spec:
        path = DATA / "images" / img["file"]
        b64 = base64.b64encode(path.read_bytes()).decode()
        for t in img["tasks"]:
            if quick and t["task_id"] not in QUICK_TASKS:
                continue
            if errors >= 3:
                runs.append({"task_id": t["task_id"], "status": "skipped", "error": "aborted after 3 errors"})
                continue
            msgs = [{"role": "system", "content": p["system"]},
                    {"role": "user", "content": render(p["user"], task_prompt=t["prompt"]), "images": [b64]}]
            rec = {"image": img["file"], "kind": img["kind"], "task_id": t["task_id"],
                   "prompt_id": p["id"], "prompt_version": p["version"]}
            try:
                r = client.chat(model, msgs, think=None, options=OPTS)
                rec.update(status="ok", **r)
                errors = 0
            except OllamaError as e:
                rec.update(status="error", error=str(e)[:400])
                errors += 1
            if rec["status"] == "ok":
                out = rec["content"]
                if t.get("expected_facts"):
                    h, n, missed = fact_hits(out, t["expected_facts"])
                    rec.update(fact_hit=h, fact_total=n, fact_rate=round(h / n, 3), missed_facts=missed)
                if t.get("expected_numbers"):
                    got = numbers_in(out)
                    exp = [normalize(x) for x in t["expected_numbers"]]
                    found = [x for x in exp if x in got]
                    rec.update(number_recall=round(len(found) / len(exp), 3),
                               missing_numbers=[x for x in exp if x not in got])
                if t.get("json"):
                    obj, err = extract_json(out)
                    rec["json_valid"] = obj is not None
                # combined score: mean of available sub-scores
                subs = [rec[k] for k in ("fact_rate", "number_recall") if k in rec]
                rec["score"] = round(sum(subs) / len(subs), 3) if subs else None
            log(f"  {t['task_id']:15s} {rec['status']} {rec.get('wall_s', 0):6.1f}s score={rec.get('score')}")
            runs.append(rec)
            append_jsonl(os.path.join(out_dir, "lvm_runs.jsonl"), rec)
    ok = [r for r in runs if r.get("status") == "ok"]
    by_kind = {}
    for r in ok:
        by_kind.setdefault(r["kind"], []).append(r["score"])
    return {"model": model, "status": "ok" if ok else "error", "options": OPTS, "calls": len(runs),
            "ok": len(ok), "errors": sum(r.get("status") == "error" for r in runs),
            "score_mean": mean([r.get("score") for r in ok]),
            "score_by_kind": {k: mean(v) for k, v in by_kind.items()},
            "per_task": {r["task_id"]: {"score": r.get("score"), "wall_s": r.get("wall_s"),
                                        "missing": r.get("missed_facts", []) + r.get("missing_numbers", [])}
                         for r in ok},
            "wall_s_p50": pct([r.get("wall_s") for r in ok], 50),
            "first_call_load_s": ok[0].get("load_s") if ok else None,
            "tokens_per_s_mean": mean([r.get("tokens_per_s") for r in ok]),
            "prompt_tokens_mean": mean([r.get("prompt_eval_count") for r in ok])}


def main():
    setup_utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = a.out or str(DATA.parent / "results" / ("lvm-" + time.strftime("%Y%m%d-%H%M%S")))
    os.makedirs(out, exist_ok=True)
    res = run(Ollama(a.host), out, a.quick)
    write_json(os.path.join(out, "lvm_results.json"), res)
    print(f"saved -> {out}")


if __name__ == "__main__":
    main()
