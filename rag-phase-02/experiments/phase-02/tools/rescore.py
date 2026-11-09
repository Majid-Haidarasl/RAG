#!/usr/bin/env python3
"""Re-score a finished run with the CURRENT scoring code and gold data (no model calls).

  python3 experiments/phase-02/tools/rescore.py experiments/phase-02/results/<run_id>

Model outputs are not changed; only the automatic scoring is recomputed. Writes
<run_dir>/rescored.json. judge_summary rows are reported as-run (their rubric changed and
needs a real re-run).
"""
import copy
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from common import CONFIG, DATA, fact_hits, mean, normalize, read_jsonl, setup_utf8, write_json  # noqa: E402
import run_llm_test as L  # noqa: E402


def rescore_llm(rows):
    gold = {q["qid"]: q for q in read_jsonl(DATA / "gold_questions.jsonl")}
    with open(DATA / "llm_cases.json", encoding="utf-8") as f:
        cases = json.load(f)
    with open(CONFIG / "prompt-registry.json", encoding="utf-8") as f:
        schemas = json.load(f)["schemas"]
    judge_exp = {c["case_id"]: c["expected"] for c in cases["judge"]}
    out = []
    for r in rows:
        r = copy.deepcopy(r)
        if r.get("status") != "ok":
            out.append(r)
            continue
        t = r["task"]
        if t == "qa":
            qid, kind = r["case_id"].rsplit("-", 1)
            L.score_qa(r, gold[qid], kind, r["context_lang"])
        elif t == "refusal":
            L.score_refusal(r)
        elif t == "summary":
            lang, level = r["case_id"].split("-", 1)
            L.score_summary(r, cases["summary"], lang, level)
        elif t == "decompose":
            L.score_decompose(r, cases["decompose"], schemas["decompose_schema"])
        elif t == "judge":
            cid = r["case_id"].rsplit("-r", 1)[0]
            L.score_judge(r, schemas["judge_schema"], 18, judge_exp.get(cid))
        out.append(r)
    return out


def rescore_lvm(rows):
    with open(DATA / "images" / "images.json", encoding="utf-8") as f:
        tasks = {t["task_id"]: t for img in json.load(f)["images"] for t in img["tasks"]}
    out = []
    for r in rows:
        r = copy.deepcopy(r)
        t = tasks.get(r.get("task_id"))
        if r.get("status") == "ok" and t:
            subs = []
            if t.get("expected_facts"):
                h, n, missed = fact_hits(r["content"], t["expected_facts"])
                r.update(fact_rate=round(h / n, 3), missed_facts=missed)
                subs.append(r["fact_rate"])
            if t.get("expected_numbers"):
                got = set(re.findall(r"\d+(?:\.\d+)?", normalize(r["content"])))
                exp = [normalize(x) for x in t["expected_numbers"]]
                r["number_recall"] = round(sum(x in got for x in exp) / len(exp), 3)
                r["missing_numbers"] = [x for x in exp if x not in got]
                subs.append(r["number_recall"])
            r["score"] = round(sum(subs) / len(subs), 3) if subs else None
        out.append(r)
    return out


def main():
    setup_utf8()
    run_dir = sys.argv[1]
    llm_rows = read_jsonl(os.path.join(run_dir, "llm_runs.jsonl"))
    lvm_path = os.path.join(run_dir, "lvm_runs.jsonl")
    lvm_rows = read_jsonl(lvm_path) if os.path.exists(lvm_path) else []  # e.g. --only llm
    new_llm = rescore_llm(llm_rows)
    new_lvm = rescore_lvm(lvm_rows)
    agg = L.aggregate(new_llm)
    lvm_ok = [r for r in new_lvm if r.get("status") == "ok"]
    res = {"note": "scores recomputed with kit scoring/data of this version; model outputs unchanged",
           "llm": agg,
           "lvm": {"score_mean": mean([r.get("score") for r in lvm_ok]) if lvm_ok else None,
                   "per_task": {r["task_id"]: r.get("score") for r in lvm_ok}},
           "changed_cases": []}
    for a, b in zip(llm_rows, new_llm):
        for k in ("fact_rate", "citation_ok", "false_refusal", "executor_coverage", "executor_name_exact_rate"):
            if a.get(k) != b.get(k) and k in b:
                res["changed_cases"].append({"task": b["task"], "case_id": b["case_id"], "think": b["think"],
                                             "metric": k, "as_run": a.get(k), "rescored": b.get(k)})
    for a, b in zip(lvm_rows, new_lvm):
        if a.get("score") != b.get("score"):
            res["changed_cases"].append({"task": "lvm", "case_id": b["task_id"], "metric": "score",
                                         "as_run": a.get("score"), "rescored": b.get("score")})
    write_json(os.path.join(run_dir, "rescored.json"), res)
    for c in res["changed_cases"]:
        print(f"{c['task']:10s} {c['case_id']:22s} {c['metric']:24s} {c['as_run']} -> {c['rescored']}")
    print(json.dumps(agg["quality_think_off"], ensure_ascii=False, indent=1))
    print("LVM", res["lvm"])
    print(f"saved -> {os.path.join(run_dir, 'rescored.json')}")


if __name__ == "__main__":
    main()
