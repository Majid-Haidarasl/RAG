#!/usr/bin/env python3
"""Run the whole Phase 2 baseline: env check -> embedding -> LLM -> LVM, with VRAM tracking.

  python3 experiments/phase-02/run_all.py --quick     # ~3-5 min smoke run
  python3 experiments/phase-02/run_all.py             # full run (~8-10 min on RTX 3060, measured 7.2)
  python3 experiments/phase-02/run_all.py --only vram # co-residency check only (~1 min)

Outputs: experiments/phase-02/results/<timestamp>/{results.json, summary.md, llm_runs.jsonl,
lvm_runs.jsonl, embedding_details.json} + results/<timestamp>.zip (send this zip back).
"""
import argparse
import os
import sys
import threading
import time
import traceback
import zipfile

sys.path.insert(0, os.path.dirname(__file__))
import check_env  # noqa: E402
import run_embedding_test  # noqa: E402
import run_llm_test  # noqa: E402
import run_lvm_test  # noqa: E402
from common import (DEFAULT_HOST, KIT_VERSION, MODELS, RESULTS, Ollama, log, nvidia_smi,  # noqa: E402
                    setup_utf8, vram_snapshot, write_json)


class GpuSampler(threading.Thread):
    """Samples nvidia-smi every `interval` s and keeps the peak used memory per stage."""

    def __init__(self, interval=2.0):
        super().__init__(daemon=True)
        self.interval, self.stage, self.peaks, self._halt = interval, "start", {}, threading.Event()
        self.enabled = isinstance(nvidia_smi(), list)

    def run(self):
        while self.enabled and not self._halt.is_set():
            g = nvidia_smi()
            if isinstance(g, list) and g:
                used = g[0]["mem_used_mib"] or 0
                p = self.peaks.setdefault(self.stage, {"peak_used_mib": 0, "peak_util_pct": 0})
                p["peak_used_mib"] = max(p["peak_used_mib"], used)
                p["peak_util_pct"] = max(p["peak_util_pct"], g[0]["util_pct"] or 0)
            self._halt.wait(self.interval)

    def stop(self):
        self._halt.set()


def co_residency(client, env, sampler, R):
    """Measure the real RAG layout: start from an empty GPU, load embedding + LLM, then add the LVM."""
    res = {}
    if not all(env["models"].get(r, {}).get("present") for r in ("embedding", "llm")):
        return {"status": "skipped", "error": "embedding or llm model missing"}
    stuck = client.unload_all()
    base = vram_snapshot(client, "co-res: empty", settle_s=3)
    R["vram"].append(base)
    res["empty_unload_ok"] = not stuck
    sampler.stage = "co-resident"
    try:
        client.embed(MODELS["embedding"], ["co-residency check"])
        client.chat(MODELS["llm"], [{"role": "user", "content": "ok"}], think=False,
                    options={"num_predict": 1, "num_ctx": 8192})
        snap = vram_snapshot(client, "co-res: embed+llm", settle_s=2)
        R["vram"].append(snap)
        res["embed_llm"] = snap
        if env["models"].get("lvm", {}).get("present"):
            import base64
            from common import DATA
            img = base64.b64encode((DATA / "images" / "revenue_table.png").read_bytes()).decode()
            client.chat(MODELS["lvm"], [{"role": "user", "content": "Total revenue?", "images": [img]}],
                        options={"num_predict": 8, "num_ctx": 8192})
            snap3 = vram_snapshot(client, "co-res: embed+llm+lvm", settle_s=2)
            R["vram"].append(snap3)
            res["all_three"] = snap3
    except Exception as e:  # noqa
        R["stage_errors"].append(f"co-residency: {e}")
        res["error"] = str(e)
    finally:
        client.unload_all()
    res["status"] = "ok" if "embed_llm" in res else "error"
    return res


def fmt(x, nd=2):
    if x is None:
        return "n/a"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def build_summary(R) -> tuple[str, str]:
    env, emb, llm, lvm = R["env"], R.get("embedding", {}), R.get("llm", {}), R.get("lvm", {})
    gpu = env.get("gpu")
    gname = gpu[0]["name"] if isinstance(gpu, list) and gpu else "n/a"
    L = [f"# Phase 2 offline model baseline — run {R['run_id']}", "",
         f"- Kit {R['kit_version']} | mode: {'QUICK' if R['quick'] else 'FULL'} | total {fmt(R['total_minutes'])} min",
         f"- Ollama {env.get('ollama', {}).get('version')} | Python {env.get('python')} | GPU {gname}",
         f"- Models: {', '.join(f'{k}={v}' for k, v in MODELS.items())}", ""]
    L += ["## Embedding (bge-m3)", ""]
    if emb.get("status") == "ok":
        L += [f"- dim {emb['embedding_dim']} | cold first call {fmt(emb['cold_first_call_s'])} s | "
              f"single-text latency mean {fmt(emb['single_text_latency_ms']['mean'])} ms | "
              f"batch {fmt(emb['batch_ms_per_chunk'])} ms/chunk", "",
              "| mode | n | R@1 | R@3 | R@5 | MRR | MP-01 (R@5≥0.80, MRR≥0.60) |", "|---|---|---|---|---|---|---|"]
        for m, v in emb["modes"].items():
            L.append(f"| {m} | {v['n']} | {fmt(v['recall@1'])} | {fmt(v['recall@3'])} | {fmt(v['recall@5'])} | "
                     f"{fmt(v['mrr'])} | {'pass' if v['meets_MP-01'] else 'FAIL'} |")
        pp = emb["parallel_pair_cosine"]
        L += ["", f"- FA↔EN parallel-chunk cosine {fmt(pp['parallel_mean'], 3)} vs non-parallel "
                  f"{fmt(pp['non_parallel_mean'], 3)} (gap {fmt(pp['gap'], 3)})", ""]
    else:
        L += [f"- {emb.get('status', 'skipped')}: {emb.get('error', '')}", ""]
    L += ["## LLM (qwen3:8b)", ""]
    if llm.get("status") == "ok":
        L += [f"- calls {llm['calls']} | ok {llm['ok']} | errors {llm['errors']}", "",
              "| think | n | tok/s | TTFT p50 s | first answer token p50 s | wall p50 s | wall p95 s | out tokens | truncated |",
              "|---|---|---|---|---|---|---|---|---|"]
        for k, v in llm["performance"].items():
            L.append(f"| {k} | {v['n']} | {fmt(v['tokens_per_s_mean'], 1)} | {fmt(v['ttft_s_p50'])} | "
                     f"{fmt(v['ttfc_s_p50'])} | {fmt(v['wall_s_p50'])} | {fmt(v['wall_s_p95'])} | "
                     f"{fmt(v['eval_tokens_mean'], 0)} | {fmt(v['truncated_rate'])} |")
        L += ["", "| quality (think off) | values |", "|---|---|"]
        for k, v in llm["quality_think_off"].items():
            L.append(f"| {k} | " + ", ".join(f"{a}={fmt(b)}" for a, b in v.items()) + " |")
        if llm.get("think_comparison"):
            L += ["", "| think on vs off | metric | off | on | wall off→on s | tokens off→on |", "|---|---|---|---|---|---|"]
            for p in llm["think_comparison"]:
                L.append(f"| {p['task']} {p['case_id']} | {p['metric']} | {fmt(p['off'])} | {fmt(p['on'])} | "
                         f"{fmt(p['wall_off_s'], 1)}→{fmt(p['wall_on_s'], 1)} | {p['tokens_off']}→{p['tokens_on']} |")
        L.append("")
    else:
        L += [f"- {llm.get('status', 'skipped')}: {llm.get('error', '')}", ""]
    L += ["## LVM (qwen2.5vl:3b)", ""]
    if lvm.get("status") == "ok":
        L += [f"- score mean {fmt(lvm['score_mean'])} | wall p50 {fmt(lvm['wall_s_p50'])} s | "
              f"tok/s {fmt(lvm['tokens_per_s_mean'], 1)} | prompt tokens/image ≈ {fmt(lvm['prompt_tokens_mean'], 0)}", "",
              "| task | score | wall s | missing |", "|---|---|---|---|"]
        for t, v in lvm["per_task"].items():
            L.append(f"| {t} | {fmt(v['score'])} | {fmt(v['wall_s'], 1)} | {', '.join(map(str, v['missing']))[:80]} |")
        L.append("")
    else:
        L += [f"- {lvm.get('status', 'skipped')}: {lvm.get('error', '')}", ""]
    L += ["## VRAM", ""]
    for s in R["vram"]:
        ps = "; ".join(f"{m['name']} {m['size_vram_mb']}MB/{m['size_mb']}MB ctx={m['context_length']}"
                       for m in s["ollama_ps"]) or "no model loaded"
        g = s["nvidia_smi"]
        used = f"{g[0]['mem_used_mib']:.0f} MiB used" if isinstance(g, list) and g else "nvidia-smi n/a"
        flags = (f" | DUPLICATE runners: {s['duplicates']}" if s.get("duplicates") else "") + \
                (f" | partly on CPU: {s['partially_offloaded']}" if s.get("partially_offloaded") else "")
        L.append(f"- {s['label']}: {ps} | {used}{flags}")
    for st, p in R.get("gpu_peaks", {}).items():
        L.append(f"- peak during {st}: {p['peak_used_mib']:.0f} MiB, util {p['peak_util_pct']:.0f}%")
    md = "\n".join(L) + "\n"

    # compact copy-paste block
    C = [f"P2 {R['run_id']} {'QUICK' if R['quick'] else 'FULL'} {fmt(R['total_minutes'])}min "
         f"ollama={env.get('ollama', {}).get('version')} gpu={gname}"]
    if emb.get("status") == "ok":
        C.append("EMB dim=%s cold=%ss lat=%sms batch=%s/%sms " % (
                     emb["embedding_dim"], fmt(emb["cold_first_call_s"]), fmt(emb["single_text_latency_ms"]["mean"], 0),
                     fmt(emb.get("batch_ms_per_chunk"), 0), fmt(emb.get("batch_warm_ms_per_chunk"), 0)) +
                 " ".join(f"{m}:R1={fmt(v['recall@1'])}/R5={fmt(v['recall@5'])}/MRR={fmt(v['mrr'])}"
                          for m, v in emb["modes"].items()))
    else:
        C.append(f"EMB {emb.get('status', 'not run')} {emb.get('error', '')[:120]}")
    if llm.get("status") == "ok":
        for k, v in llm["performance"].items():
            C.append(f"LLM {k} n={v['n']} tok/s={fmt(v['tokens_per_s_mean'], 1)} ttft={fmt(v['ttft_s_p50'])} "
                     f"ans1st={fmt(v['ttfc_s_p50'])} wall50={fmt(v['wall_s_p50'])} wall95={fmt(v['wall_s_p95'])} "
                     f"trunc={fmt(v['truncated_rate'])} leak={fmt(v['think_leak_rate'])}")
        for k, v in llm["quality_think_off"].items():
            C.append(f"Q {k} " + " ".join(f"{a}={fmt(b)}" for a, b in v.items() if a != "totals") +
                     (f" totals={v['totals']}" if "totals" in v else ""))
        for p in llm.get("think_comparison", []):
            C.append(f"T {p['task']}:{p['case_id']} {p['metric']} off={fmt(p['off'])} on={fmt(p['on'])} "
                     f"wall={fmt(p['wall_off_s'], 1)}->{fmt(p['wall_on_s'], 1)}")
        C.append(f"LLM calls={llm['calls']} ok={llm['ok']} err={llm['errors']}")
    else:
        C.append(f"LLM {llm.get('status', 'not run')} {llm.get('error', '')[:120]}")
    if lvm.get("status") == "ok":
        C.append(f"LVM mean={fmt(lvm['score_mean'])} wall50={fmt(lvm['wall_s_p50'])} " +
                 " ".join(f"{t}={fmt(v['score'])}" for t, v in lvm["per_task"].items()))
    else:
        C.append(f"LVM {lvm.get('status', 'not run')} {lvm.get('error', '')[:120]}")
    for s in R["vram"]:
        g = s["nvidia_smi"]
        C.append(f"VRAM {s['label']}: " + ",".join(f"{m['name']}={m['size_vram_mb']}MB" for m in s["ollama_ps"]) +
                 (f" smi={g[0]['mem_used_mib']:.0f}MiB" if isinstance(g, list) and g else "") +
                 (f" DUP={s['duplicates']}" if s.get("duplicates") else "") +
                 (f" CPU-OFFLOAD={s['partially_offloaded']}" if s.get("partially_offloaded") else ""))
    for st, p in R.get("gpu_peaks", {}).items():
        C.append(f"PEAK {st}={p['peak_used_mib']:.0f}MiB")
    if R.get("stage_errors"):
        C.append("ERR " + " | ".join(R["stage_errors"])[:400])
    return md, "\n".join(C)


def main():
    setup_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--quick", action="store_true", help="~3-5 min smoke run")
    ap.add_argument("--only", choices=["embed", "llm", "lvm", "vram"], action="append",
                    help="run only these stages (repeatable); 'vram' = co-residency check only (~1 min)")
    ap.add_argument("--no-think", action="store_true", help="skip think-on comparisons (faster)")
    ap.add_argument("--timeout", type=float, default=300, help="per-request timeout seconds")
    ap.add_argument("--keep-loaded", action="store_true",
                    help="do not unload each model after its stage (default: unload, so VRAM per model is clean)")
    a = ap.parse_args()

    t0 = time.time()
    run_id = time.strftime("%Y%m%d-%H%M%S")
    out = RESULTS / run_id
    out.mkdir(parents=True, exist_ok=True)
    stages = a.only or ["embed", "llm", "lvm", "vram"]
    client = Ollama(a.host, timeout=a.timeout)

    log("checking environment ...")
    env = check_env.collect(a.host)
    code = check_env.print_summary(env)
    R = {"kit_version": KIT_VERSION, "run_id": run_id, "quick": a.quick, "stages": stages, "env": env,
         "vram": [], "stage_errors": []}
    if code == 1:
        R["stage_errors"].append("ollama unreachable")
        write_json(out / "results.json", R)
        log("Ollama is not reachable — start it (sudo systemctl start ollama) and re-run.")
        sys.exit(1)
    R["vram"].append(vram_snapshot(client, "before"))
    sampler = GpuSampler()
    sampler.start()
    role_of = {"embed": "embedding", "llm": "llm", "lvm": "lvm"}
    if not a.keep_loaded:
        stuck = client.unload_all()
        if stuck:
            R["stage_errors"].append(f"could not unload before start: {stuck}")
    for st in stages:
        if st == "vram":
            continue
        role = role_of[st]
        if not env["models"].get(role, {}).get("present"):
            R[role] = {"status": "skipped", "error": f"model {MODELS[role]} missing"}
            R["stage_errors"].append(f"{st}: model missing")
            continue
        if not a.keep_loaded:                       # clean VRAM: only this stage's model may be resident
            stuck = client.unload_all()
            if stuck:
                R["stage_errors"].append(f"{st}: still loaded before stage: {stuck}")
        sampler.stage = st
        log(f"===== stage: {st} =====")
        ts = time.time()
        try:
            if st == "embed":
                R["embedding"] = run_embedding_test.run(client, str(out), a.quick)
            elif st == "llm":
                R["llm"] = run_llm_test.run(client, str(out), a.quick, not a.no_think)
            else:
                R["lvm"] = run_lvm_test.run(client, str(out), a.quick)
        except Exception as e:  # keep going with other stages
            traceback.print_exc()
            R[role] = {"status": "error", "error": f"{type(e).__name__}: {e}"}
            R["stage_errors"].append(f"{st}: {type(e).__name__}: {e}")
        R.setdefault("stage_minutes", {})[st] = round((time.time() - ts) / 60, 2)
        R["vram"].append(vram_snapshot(client, f"after-{st}"))
        if not a.keep_loaded and not client.unload(MODELS[role]):
            R["stage_errors"].append(f"{st}: {MODELS[role]} did not unload")
        write_json(out / "results.json", R)        # checkpoint after each stage
    if "vram" in stages:
        log("===== stage: vram (co-residency) =====")
        R["co_residency"] = co_residency(client, env, sampler, R)
    sampler.stop()
    R["gpu_peaks"] = sampler.peaks
    R["total_minutes"] = round((time.time() - t0) / 60, 2)
    md, block = build_summary(R)
    R["copy_paste_block"] = block
    write_json(out / "results.json", R)
    (out / "summary.md").write_text(md, encoding="utf-8")
    zpath = RESULTS / f"phase02-results-{run_id}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(out.iterdir()):
            z.write(f, f"{run_id}/{f.name}")
    print("\n" + "=" * 70)
    print("COPY EVERYTHING BETWEEN THE LINES AND SEND IT BACK  /  این بخش را کپی کن و بفرست")
    print("-" * 70)
    print(block)
    print("-" * 70)
    print(f"Full results: {out}")
    print(f"Zip to send:  {zpath}")
    print("=" * 70)


if __name__ == "__main__":
    main()
