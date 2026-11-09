#!/usr/bin/env python3
"""LLM baseline (qwen3:8b): grounded Q&A with citations, refusal, TransferPackage summaries
(2 detail levels), sub-issue decomposition to JSON, LLM-as-judge (/20). FA + EN, think on/off.

Every call is logged to llm_runs.jsonl (prompt id/version, output, timings) for human review.
"""
import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from common import (CONFIG, DATA, DEFAULT_HOST, MODELS, Ollama, OllamaError, append_jsonl, extract_json,
                    fact_hits, load_prompts, log, mean, normalize, pct, read_jsonl, render,
                    setup_utf8, write_json)

LANG_NAME = {"fa": "Persian (Farsi)", "en": "English"}
CITE_RE = re.compile(r"\[\s*((?:fa|en)-[A-Z]{2,3}-\d{3}-c\d+)\s*\]")
DOC_RE = re.compile(r"^AR-[A-Z]{2,3}-\d{3}$")
REFUSAL_TOKEN = "INSUFFICIENT_CONTEXT"
REFUSAL_PHRASES = ["insufficient_context", "در منابع موجود نیست", "در متن موجود نیست", "اطلاعاتی وجود ندارد",
                   "not contain", "not in the context", "not provided", "not mentioned", "does not mention"]
BASE_OPTS = {"temperature": 0.2, "top_p": 0.9, "num_ctx": 8192, "seed": 42}
THINK_NUM_PREDICT = 4096   # kit 0.2.1: 2048 truncated one think-on decomposition (run 191910); truncation is reported, not hidden
REPEAT_OPTS = {"temperature": 0.7, "top_p": 0.9, "num_ctx": 8192}   # stability under sampling (MP-08)


class Runner:
    def __init__(self, client, out_dir):
        self.client, self.out_dir = client, out_dir
        self.model = MODELS["llm"]
        self.runs, self.consecutive_errors = [], 0

    def call(self, task, case_id, lang, think, prompt, messages, fmt=None, opts=None, num_predict=None, extra=None):
        if self.consecutive_errors >= 3:
            rec = {"task": task, "case_id": case_id, "lang": lang, "think": think, "status": "skipped",
                   "error": "aborted after 3 consecutive errors"}
            self.runs.append(rec)
            return rec
        options = dict(opts or BASE_OPTS)
        options["num_predict"] = num_predict or (THINK_NUM_PREDICT if think else 1024)
        rec = {"task": task, "case_id": case_id, "lang": lang, "think": think,
               "prompt_id": prompt["id"], "prompt_version": prompt["version"],
               "format": "schema" if isinstance(fmt, dict) else fmt, "options": options}
        t = time.perf_counter()
        try:
            r = self.client.chat(self.model, messages, think=think, fmt=fmt, options=options)
            rec.update(status="ok", **r)
            rec["truncated_in_thinking"] = bool(think and r.get("done_reason") == "length" and not r.get("content"))
            self.consecutive_errors = 0
        except OllamaError as e:
            rec.update(status="error", error=str(e)[:400], wall_s=round(time.perf_counter() - t, 3))
            self.consecutive_errors += 1
        if extra:
            rec.update(extra)
        log(f"  {task:10s} {case_id:14s} think={'on ' if think else 'off'} "
            f"{rec.get('status')} {rec.get('wall_s', 0):6.1f}s tok/s={rec.get('tokens_per_s')}")
        return rec

    def save(self, rec):
        self.runs.append(rec)
        append_jsonl(os.path.join(self.out_dir, "llm_runs.jsonl"), rec)


def build_context(q_topic, lang, chunks_by_id, topics, salt):
    i = topics.index(q_topic)
    ids = [f"{lang}-{q_topic}-c1", f"{lang}-{topics[(i + 3) % len(topics)]}-c1",
           f"{lang}-{topics[(i + 7) % len(topics)]}-c1"]
    pos = sum(map(ord, salt)) % 3
    ids.insert(pos, ids.pop(0))
    return ids, "\n\n".join(f"[{cid}]\n{chunks_by_id[cid]['text']}" for cid in ids)


def is_refusal(text):
    n = normalize(text)
    return REFUSAL_TOKEN.lower() in n or any(p in n for p in REFUSAL_PHRASES)


def validate_schema(obj, schema):
    """Minimal JSON-schema subset validator (type/required/enum/items/min/maxItems)."""
    errs = []

    def chk(o, s, path):
        t = s.get("type")
        types = {"object": dict, "array": list, "string": str, "integer": int}
        if t and (not isinstance(o, types[t]) or (t == "integer" and isinstance(o, bool))):
            errs.append(f"{path}: expected {t}")
            return
        if "enum" in s and o not in s["enum"]:
            errs.append(f"{path}: {o!r} not in enum")
        if t == "object":
            for k in s.get("required", []):
                if k not in o:
                    errs.append(f"{path}.{k}: missing")
            for k, sub in s.get("properties", {}).items():
                if k in o:
                    chk(o[k], sub, f"{path}.{k}")
        if t == "array":
            if "minItems" in s and len(o) < s["minItems"]:
                errs.append(f"{path}: fewer than {s['minItems']} items")
            if "maxItems" in s and len(o) > s["maxItems"]:
                errs.append(f"{path}: more than {s['maxItems']} items")
            for j, it in enumerate(o):
                chk(it, s.get("items", {}), f"{path}[{j}]")

    chk(obj, schema, "$")
    return errs


def words(text):
    return len(re.findall(r"\S+", text or ""))


# ------------------------------------------------------------------ tasks
# ------------------------------------------------------------------ scoring (pure, reusable by tools/rescore.py)
def score_qa(rec, q, kind, ctx_lang):
    facts = q["expected_facts"] if kind == "mono" else q["cross_lingual_facts"]
    hit, tot, missed = fact_hits(rec["content"], facts)
    rel = set(q["relevant"][ctx_lang])
    cited = CITE_RE.findall(rec["content"])
    rec.update(fact_hit=hit, fact_total=tot, fact_rate=round(hit / tot, 3) if tot else None,
               all_facts=hit == tot, missed_facts=missed, cited_ids=cited,
               citation_ok=any(c in rel for c in cited),
               citation_precision=round(sum(c in rel for c in cited) / len(cited), 3) if cited else 0.0,
               false_refusal=is_refusal(rec["content"]))
    return rec


def score_refusal(rec):
    rec.update(refused=is_refusal(rec["content"]), exact_token=REFUSAL_TOKEN in rec["content"])
    return rec


def score_summary(rec, spec, lang, level):
    hit, tot, missed = fact_hits(rec["content"], spec["expected_facts"][level][lang])
    w = words(rec["content"])
    rec.update(fact_hit=hit, fact_total=tot, fact_rate=round(hit / tot, 3), missed_facts=missed,
               words=w, within_limit=w <= spec["max_words"][level])
    return rec


def score_decompose(rec, spec, schema):
    obj, err = extract_json(rec["content"])
    rec["json_valid"] = obj is not None
    rec["json_error"] = err
    if obj is None:
        rec["schema_valid"] = False
        return rec
    errs = validate_schema(obj, schema)
    rec["schema_valid"] = not errs
    rec["schema_errors"] = errs[:8]
    subs = obj.get("sub_issues", []) if isinstance(obj, dict) else []
    subs = [s for s in subs if isinstance(s, dict)]
    doms = {str(s.get("domain", "")).upper() for s in subs}
    rec["n_sub_issues"] = len(subs)
    rec["domains"] = sorted(doms)
    exp = spec["expected_domains"]
    # strict: the expected domain label must be used
    rec["domain_recall"] = round(sum(x in doms for x in exp) / len(exp), 3)
    match = []
    for dom, alts_groups in spec["expected_executors"].items():
        ex_text = " ".join(str(s.get("suggested_executor", "")) for s in subs
                           if str(s.get("domain", "")).upper() == dom)
        match.append(any(fact_hits(ex_text, [g])[0] for g in alts_groups) if ex_text else False)
    rec["executor_match_rate"] = round(sum(match) / len(match), 3)
    # label-independent: is each expected work stream owned by an expected executor somewhere?
    all_ex = " ".join(str(s.get("suggested_executor", "")) for s in subs)
    cov = [any(fact_hits(all_ex, [g])[0] for g in groups) for groups in spec["expected_executors"].values()]
    rec["executor_coverage"] = round(sum(cov) / len(cov), 3)
    # exact copy of executor names (detects Persian name corruption, e.g. "جوتادی")
    allowed = spec.get("allowed_executors", {}).get(rec.get("lang"), [])
    if allowed:
        names = [str(s.get("suggested_executor", "")).strip() for s in subs]
        parts = [p.strip() for n in names for p in re.split(r"\s*[+،,/]\s*|\s+و\s+", n) if p.strip()]
        bad = [p for p in parts if normalize(p) not in {normalize(a) for a in allowed}]
        rec["executor_name_exact_rate"] = round(1 - len(bad) / len(parts), 3) if parts else None
        rec["executor_name_errors"] = bad
    docs = [d_ for s in subs for d_ in (s.get("related_docs") or []) if isinstance(d_, str)]
    rec["doc_ids_wellformed_rate"] = round(sum(bool(DOC_RE.match(x.strip())) for x in docs) / len(docs), 3) if docs else None
    return rec


def score_judge(rec, schema, threshold, expected=None):
    obj, err = extract_json(rec["content"])
    rec["json_valid"] = obj is not None
    rec["json_error"] = err
    if obj is None:
        rec["schema_valid"] = False
        return rec
    errs = validate_schema(obj, schema)
    rec["schema_valid"] = not errs
    rec["schema_errors"] = errs[:8]
    sc = obj.get("scores") if isinstance(obj, dict) else None
    try:
        s = sum(int(v) for v in sc.values())
        rec["sum_consistent"] = s == int(obj.get("total"))
        rec["total"] = int(obj.get("total"))
        rec["computed_total"] = s
        rec["verdict"] = obj.get("verdict")
        rec["verdict_matches_threshold"] = (obj.get("verdict") == "accept") == (s >= threshold)
        if expected:
            rec["verdict_correct"] = (s >= threshold) == (expected == "accept")
    except Exception:
        rec["sum_consistent"] = False
    return rec


# ------------------------------------------------------------------ tasks
def task_qa(R, P, gold, chunks_by_id, topics, quick, think_cases):
    p = P["qa.grounded"]
    if quick:
        sel = [q for q in gold if q["qid"] in ("FA-01", "FA-09", "FA-18", "FA-20", "EN-03", "EN-07")]
        cross = [q for q in gold if q["qid"] == "FA-09"]
    else:
        sel = gold
        cross = [q for q in gold if q.get("cross_lingual_facts")]
    jobs = [(q, q["lang"], q["lang"], False, "mono") for q in sel]
    jobs += [(q, "en" if q["lang"] == "fa" else "fa", q["lang"], False, "cross") for q in cross]
    jobs += [(q, ctx, ans, True, kind) for (q, ctx, ans, _, kind) in list(jobs)
             if (q["qid"], kind) in think_cases]
    for q, ctx_lang, ans_lang, think, kind in jobs:
        ids, ctx = build_context(q["topic"], ctx_lang, chunks_by_id, topics, q["qid"])
        msgs = [{"role": "system", "content": render(p["system"], answer_language=LANG_NAME[ans_lang])},
                {"role": "user", "content": render(p["user"], context=ctx, question=q["question"])}]
        rec = R.call("qa", f"{q['qid']}-{kind}", ans_lang, think, p, msgs,
                     extra={"qa_kind": kind, "context_lang": ctx_lang, "context_ids": ids})
        if rec["status"] == "ok":
            score_qa(rec, q, kind, ctx_lang)
        R.save(rec)


def task_refusal(R, P, cases, chunks_by_id, quick, think_ids):
    p = P["qa.grounded"]
    sel = cases if not quick else [c for c in cases if c["case_id"] in ("REF-FA-01", "REF-EN-01")]
    jobs = [(c, False) for c in sel] + [(c, True) for c in sel if c["case_id"] in think_ids]
    for c, think in jobs:
        ctx = "\n\n".join(f"[{cid}]\n{chunks_by_id[cid]['text']}" for cid in c["context_chunks"])
        msgs = [{"role": "system", "content": render(p["system"], answer_language=LANG_NAME[c["lang"]])},
                {"role": "user", "content": render(p["user"], context=ctx, question=c["question"])}]
        rec = R.call("refusal", c["case_id"], c["lang"], think, p, msgs)
        if rec["status"] == "ok":
            score_refusal(rec)
        R.save(rec)


def task_summary(R, P, spec, chunks_by_id, quick, think_ids):
    p = P["summary.transfer"]
    combos = [("fa", "executive"), ("en", "technical")] if quick else \
        [(l, lv) for l in ("fa", "en") for lv in ("executive", "technical")]
    jobs = [(l, lv, False) for l, lv in combos] + [(l, lv, True) for l, lv in combos if f"{l}-{lv}" in think_ids]
    outputs = []
    for lang, level, think in jobs:
        source = spec["source_prefix"][lang] + "\n\n" + "\n\n".join(
            chunks_by_id[c]["text"] for c in spec["source_chunks"][lang])
        msgs = [{"role": "system", "content": render(p["system"], answer_language=LANG_NAME[lang])},
                {"role": "user", "content": render(p["user"], level_instruction=p["levels"][level], source=source)}]
        rec = R.call("summary", f"{lang}-{level}", lang, think, p, msgs, extra={"level": level})
        if rec["status"] == "ok":
            score_summary(rec, spec, lang, level)
            outputs.append((lang, level, think, source, rec["content"]))
        R.save(rec)
    return outputs


def task_decompose(R, P, schemas, spec, quick, think_ids):
    p = P["issue.decompose"]
    schema = schemas["decompose_schema"]
    if quick:
        jobs = [("fa", "prompt_only", 0, False), ("en", "schema", 0, False)]
    else:
        jobs = [(l, v, r, False) for l in ("fa", "en") for v in ("prompt_only", "schema") for r in range(3)]
    jobs += [(l, "prompt_only", 0, True) for l in ("fa", "en") if f"decompose-{l}" in think_ids]
    for lang, variant, rep, think in jobs:
        d = spec[lang]
        msgs = [{"role": "system", "content": render(p["system"], answer_language=LANG_NAME[lang])},
                {"role": "user", "content": render(p["user"], issue_id=spec["issue_id"], issue=d["issue"],
                                                   executors=d["executors"], documents=d["documents"])}]
        fmt = schema if variant == "schema" else None
        rec = R.call("decompose", f"{lang}-{variant}-r{rep}", lang, think, p, msgs, fmt=fmt,
                     opts=REPEAT_OPTS if rep > 0 else BASE_OPTS, num_predict=None if think else 1536,
                     extra={"variant": variant, "repeat": rep})
        if rec["status"] == "ok":
            score_decompose(rec, spec, schema)
        R.save(rec)


def judge_once(R, P, schemas, case_id, lang, source_id, source, question, answer, think, expected=None, rep=0,
               task="judge", prompt_id="judge.score"):
    p = P[prompt_id]
    msgs = [{"role": "system", "content": p["system"]},
            {"role": "user", "content": render(p["user"], source_id=source_id, source=source,
                                               question=question, answer=answer)}]
    rec = R.call(task, f"{case_id}-r{rep}", lang, think, p, msgs, opts=REPEAT_OPTS if rep > 0 else BASE_OPTS,
                 num_predict=None if think else 512, extra={"expected_verdict": expected, "repeat": rep})
    if rec["status"] == "ok":
        score_judge(rec, schemas[p.get("schema", "judge_schema")], p["threshold"], expected)
    R.save(rec)
    return rec


def task_judge(R, P, schemas, cases, chunks_by_id, quick, think_ids):
    sel = cases if not quick else [c for c in cases if c["case_id"] in ("JDG-FA-GOOD", "JDG-EN-BAD")]
    reps = 1 if quick else 2
    jobs = [(c, False, r) for c in sel for r in range(reps)] + [(c, True, 0) for c in sel if c["case_id"] in think_ids]
    for c, think, rep in jobs:
        src = chunks_by_id[c["source_chunk"]]
        judge_once(R, P, schemas, c["case_id"], c["lang"], c["source_chunk"], src["text"], c["question"],
                   c["answer"], think, c["expected"], rep)


# ------------------------------------------------------------------ aggregation
def _rate(rs, key):
    vals = [bool(r.get(key)) for r in rs if r.get("status") == "ok" and key in r]
    return round(sum(vals) / len(vals), 3) if vals else None


def aggregate(runs):
    ok = [r for r in runs if r.get("status") == "ok"]
    agg = {"calls": len(runs), "ok": len(ok), "errors": sum(r.get("status") == "error" for r in runs)}
    perf = {}
    for think in (False, True):
        rs = [r for r in ok if r["think"] == think]
        if not rs:
            continue
        perf["think_on" if think else "think_off"] = {
            "n": len(rs), "tokens_per_s_mean": mean([r.get("tokens_per_s") for r in rs]),
            "prompt_tokens_per_s_mean": mean([r.get("prompt_tokens_per_s") for r in rs]),
            "ttft_s_p50": pct([r.get("ttft_s") for r in rs], 50),
            "ttfc_s_p50": pct([r.get("ttfc_s") for r in rs], 50),
            "wall_s_p50": pct([r.get("wall_s") for r in rs], 50),
            "wall_s_p95": pct([r.get("wall_s") for r in rs], 95),
            "eval_tokens_mean": mean([r.get("eval_count") for r in rs]),
            "thinking_chars_mean": mean([r.get("thinking_chars") for r in rs]),
            "think_leak_rate": round(sum("<think>" in (r.get("content") or "") for r in rs) / len(rs), 3),
            "truncated_rate": round(sum(r.get("done_reason") == "length" for r in rs) / len(rs), 3),
            "empty_answer_after_thinking_rate": round(sum(bool(r.get("truncated_in_thinking")) for r in rs) / len(rs), 3)}
    agg["performance"] = perf
    q = {}
    off = [r for r in ok if not r["think"]]
    for kind, lang in (("mono", "fa"), ("mono", "en"), ("cross", "fa"), ("cross", "en")):
        rs = [r for r in off if r["task"] == "qa" and r.get("qa_kind") == kind and r["lang"] == lang]
        if rs:
            q[f"qa_{kind}_{lang}"] = {"n": len(rs), "fact_rate_mean": mean([r.get("fact_rate") for r in rs]),
                                       "all_facts_rate": _rate(rs, "all_facts"),
                                       "citation_ok_rate": _rate(rs, "citation_ok"),
                                       "citation_precision_mean": mean([r.get("citation_precision") for r in rs]),
                                       "false_refusal_rate": _rate(rs, "false_refusal")}
    rs = [r for r in off if r["task"] == "refusal"]
    if rs:
        q["refusal"] = {"n": len(rs), "correct_refusal_rate": _rate(rs, "refused"),
                        "exact_token_rate": _rate(rs, "exact_token")}
    for level in ("executive", "technical"):
        rs = [r for r in off if r["task"] == "summary" and r.get("level") == level]
        if rs:
            q[f"summary_{level}"] = {"n": len(rs), "fact_rate_mean": mean([r.get("fact_rate") for r in rs]),
                                     "words_mean": mean([r.get("words") for r in rs]),
                                     "within_limit_rate": _rate(rs, "within_limit")}
    for variant in ("prompt_only", "schema"):
        rs = [r for r in off if r["task"] == "decompose" and r.get("variant") == variant]
        if rs:
            q[f"decompose_{variant}"] = {"n": len(rs), "json_valid_rate": _rate(rs, "json_valid"),
                                         "schema_valid_rate": _rate(rs, "schema_valid"),
                                         "domain_recall_mean": mean([r.get("domain_recall") for r in rs]),
                                         "executor_match_mean": mean([r.get("executor_match_rate") for r in rs]),
                                         "executor_coverage_mean": mean([r.get("executor_coverage") for r in rs]),
                                         "executor_name_exact_mean": mean([r.get("executor_name_exact_rate") for r in rs]),
                                         "n_sub_issues_mean": mean([r.get("n_sub_issues") for r in rs])}
    rs = [r for r in off if r["task"] == "judge" and r.get("expected_verdict")]
    if rs:
        q["judge"] = {"n": len(rs), "json_valid_rate": _rate(rs, "json_valid"),
                      "schema_valid_rate": _rate(rs, "schema_valid"),
                      "sum_consistent_rate": _rate(rs, "sum_consistent"),
                      "verdict_accuracy": _rate(rs, "verdict_correct"),
                      "totals": {r["case_id"]: r.get("computed_total") for r in rs}}
    rs = [r for r in off if r["task"] == "judge_summary"]
    if rs:
        q["judge_on_summaries"] = {r["case_id"]: r.get("computed_total") for r in rs}
    agg["quality_think_off"] = q
    # think on vs off on identical cases
    pairs = []
    for r_on in [r for r in ok if r["think"]]:
        r_off = next((r for r in off if r["task"] == r_on["task"] and r["case_id"] == r_on["case_id"]), None)
        if not r_off:
            continue
        keyq = next((k for k in ("fact_rate", "refused", "verdict_correct", "schema_valid") if k in r_on), None)
        pairs.append({"task": r_on["task"], "case_id": r_on["case_id"], "metric": keyq,
                      "off": r_off.get(keyq), "on": r_on.get(keyq),
                      "wall_off_s": r_off.get("wall_s"), "wall_on_s": r_on.get("wall_s"),
                      "tokens_off": r_off.get("eval_count"), "tokens_on": r_on.get("eval_count")})
    agg["think_comparison"] = pairs
    return agg


def run(client: Ollama, out_dir: str, quick: bool = False, think_tests: bool = True) -> dict:
    model = MODELS["llm"]
    P = load_prompts()
    with open(CONFIG / "prompt-registry.json", encoding="utf-8") as f:
        schemas = json.load(f)["schemas"]
    chunks = read_jsonl(DATA / "chunks.jsonl")
    cbi = {c["chunk_id"]: c for c in chunks}
    topics = []
    for c in chunks:
        if c["topic"] not in topics:
            topics.append(c["topic"])
    gold = read_jsonl(DATA / "gold_questions.jsonl")
    with open(DATA / "llm_cases.json", encoding="utf-8") as f:
        cases = json.load(f)
    if quick:
        think_qa, think_ids = {("FA-18", "mono")}, set()
    else:
        think_qa = {("FA-09", "mono"), ("FA-18", "mono"), ("FA-20", "mono"), ("EN-03", "mono"),
                    ("EN-07", "mono"), ("FA-09", "cross")}
        think_ids = {"REF-FA-02", "fa-executive", "decompose-fa", "decompose-en", "JDG-FA-BAD", "JDG-EN-BAD"}
    if not think_tests:
        think_qa, think_ids = set(), set()
    R = Runner(client, out_dir)
    log(f"LLM test on {model} (quick={quick}, think_tests={think_tests})")
    try:
        _ = client.chat(model, [{"role": "user", "content": "ok"}], think=False,
                        options={"num_predict": 1, "num_ctx": 8192})
    except OllamaError as e:
        log(f"LLM warm-up failed: {e}")
        return {"model": model, "status": "error", "error": str(e)}
    log("[1/5] grounded Q&A");      task_qa(R, P, gold, cbi, topics, quick, think_qa)
    log("[2/5] refusal");           task_refusal(R, P, cases["refusal"], cbi, quick, think_ids)
    log("[3/5] transfer summaries"); outs = task_summary(R, P, cases["summary"], cbi, quick, think_ids)
    log("[4/5] decomposition JSON"); task_decompose(R, P, schemas, cases["decompose"], quick, think_ids)
    log("[5/5] LLM judge");         task_judge(R, P, schemas, cases["judge"], cbi, quick, think_ids)
    if not quick:
        for lang, level, think, source, text in outs:
            if think:
                continue
            q = P["summary.transfer"]["levels"][level]
            judge_once(R, P, schemas, f"SUM-{lang}-{level}", lang, "AR-ISS-024", source, q, text, False,
                       task="judge_summary", prompt_id="judge.summary")
    agg = aggregate(R.runs)
    return {"model": model, "status": "ok", "quick": quick, "base_options": BASE_OPTS,
            "repeat_options": REPEAT_OPTS, **agg}


def main():
    setup_utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--no-think", action="store_true", help="skip think-on comparisons")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = a.out or str(DATA.parent / "results" / ("llm-" + time.strftime("%Y%m%d-%H%M%S")))
    os.makedirs(out, exist_ok=True)
    res = run(Ollama(a.host), out, a.quick, not a.no_think)
    write_json(os.path.join(out, "llm_results.json"), res)
    print(f"saved -> {out}")


if __name__ == "__main__":
    main()
