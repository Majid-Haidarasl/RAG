#!/usr/bin/env python3
"""Tiny fake Ollama server for testing the Phase 2 kit WITHOUT models/GPU.

  python3 experiments/phase-02/tools/mock_ollama.py --port 11500 [--no-think-api] [--fail-every N]
  OLLAMA_HOST_URL=http://127.0.0.1:11500 python3 experiments/phase-02/run_all.py --quick

Outputs are canned/heuristic. Mock numbers say NOTHING about real model quality.
"""
import argparse
import hashlib
import json
import math
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODELS = [("qwen3:8b", 5_200_000_000, "qwen3", "8.2B", "Q4_K_M"),
          ("qwen2.5vl:3b", 3_200_000_000, "qwen25vl", "3.8B", "Q4_K_M"),
          ("bge-m3:latest", 1_200_000_000, "bert", "567M", "F16")]
LOADED = {}      # name -> [size, runner_count]
UNLOAD_AT = {}   # name -> time when one runner disappears
ARGS = None
COUNTER = {"n": 0}
DIM = 256


def embed(text):
    v = [0.0] * DIM
    t = re.sub(r"[۰-۹]", lambda m: str("۰۱۲۳۴۵۶۷۸۹".index(m.group())), text.lower())
    toks = re.findall(r"\w+", t)
    feats = toks + [t[i:i + 3] for i in range(len(t) - 2)]
    for f in feats:
        h = int(hashlib.md5(f.encode()).hexdigest(), 16)
        v[h % DIM] += 1.0 if (h >> 8) % 2 else -1.0
    n = math.sqrt(sum(x * x for x in v)) or 1
    return [x / n for x in v]


def purge():
    now = time.time()
    for n, t in list(UNLOAD_AT.items()):
        if now >= t:
            del UNLOAD_AT[n]
            if n in LOADED:
                LOADED[n][1] -= 1
                if LOADED[n][1] <= 0:
                    del LOADED[n]


def words(s):
    return set(re.findall(r"\w{3,}", s.lower()))


def answer_for(system, user, has_image):
    if has_image:
        return ("Board of Directors - Chair: Dr. Nima Yazdani\nChief Executive Officer - Eng. Arash Moradi\n"
                "Hardware VP - Behrouz Karimi\nTotal revenue 8,470; operating profit 1,170; 30 دقیقه; 4 ساعت")
    if "offline knowledge assistant" in system:
        q = user.split("QUESTION:", 1)[-1]
        blocks = re.findall(r"\[((?:fa|en)-[A-Z]+-\d+-c\d)\]\n(.*?)(?=\n\n\[|\n\nQUESTION:)", user, re.S)
        best = max(blocks, key=lambda b: len(words(q) & words(b[1])), default=None)
        if not best or len(words(q) & words(best[1])) < 2:
            return "INSUFFICIENT_CONTEXT the context does not contain this."
        sent = re.split(r"(?<=[.!؟?])\s", best[1].strip())[0]
        return f"{sent[:400]} [{best[0]}]"
    if "strict evaluator" in system:
        good = "[" in user.split("ANSWER:", 1)[-1]
        if "level_fit" in system:
            good = True
            s = {"faithfulness": 5, "coverage": 4, "level_fit": 5, "clarity": 5}
        else:
            s = {"faithfulness": 5, "completeness": 5, "citation": 5, "clarity": 4} if good else \
                {"faithfulness": 1, "completeness": 3, "citation": 0, "clarity": 4}
        return "```json\n" + json.dumps({"scores": s, "total": sum(s.values()),
                                         "verdict": "accept" if sum(s.values()) >= 18 else "revise",
                                         "issues": [] if good else ["wrong numbers"]}) + "\n```"
    if "TransferPackage" in system:
        src = user.split("SOURCE:", 1)[-1]
        n = 60 if "EXECUTIVE" in user else 200
        return " ".join(src.split()[:n])
    if "decompose" in system:
        return json.dumps({"issue_id": "AR-ISS-024", "sub_issues": [
            {"id": "S1", "title": "RAID/RAM compatibility", "domain": "HW", "suggested_executor": "Saeed Akbari",
             "related_docs": ["AR-HW-012", "AR-HW-015"], "rationale": "controller mismatch"},
            {"id": "S2", "title": "Windows client", "domain": "WIN", "suggested_executor": "Rouzbeh Mohseni",
             "related_docs": ["AR-SW-019"], "rationale": "client on new hardware"},
            {"id": "S3", "title": "Scope vs non-conformity", "domain": "LEG", "suggested_executor": "Mahsa Jalali",
             "related_docs": ["AR-LEG-009"], "rationale": "penalty and amendment"}]}, ensure_ascii=False)
    return "ok"


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == "/api/version":
            return self._json(200, {"version": "0.12.0-mock"})
        if self.path == "/api/tags":
            return self._json(200, {"models": [{"name": n, "model": n, "size": s, "details": {
                "family": f, "parameter_size": p, "quantization_level": q, "format": "gguf"}} for n, s, f, p, q in MODELS]})
        if self.path == "/api/ps":
            purge()
            return self._json(200, {"models": [{"name": n, "size": v[0], "size_vram": v[0], "context_length": 8192}
                                               for n, v in LOADED.items() for _ in range(v[1])]})
        self._json(404, {"error": "not found"})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        COUNTER["n"] += 1
        if ARGS.fail_every and COUNTER["n"] % ARGS.fail_every == 0:
            return self._json(500, {"error": "injected failure"})
        model = body.get("model")
        sizes = {n: s for n, s, *_ in MODELS}
        if self.path in ("/api/embed", "/api/chat", "/api/show", "/api/generate") and model not in sizes:
            return self._json(404, {"error": f"model '{model}' not found"})
        if self.path == "/api/show":
            arch = {"qwen3:8b": "qwen3", "qwen2.5vl:3b": "qwen25vl", "bge-m3:latest": "bert"}[model]
            mi = {f"{arch}.context_length": 40960 if arch == "qwen3" else 128000 if arch == "qwen25vl" else 8192}
            if arch == "bert":
                mi["bert.embedding_length"] = 1024
            caps = ["embedding"] if arch == "bert" else ["completion", "thinking"] if arch == "qwen3" else ["completion", "vision"]
            return self._json(200, {"model_info": mi, "capabilities": caps})
        if body.get("keep_alive") == 0:
            if model in LOADED:
                UNLOAD_AT.setdefault(model, time.time() + ARGS.unload_delay)
            return self._json(200, {"done": True})
        if model not in LOADED:
            LOADED[model] = [sizes[model], 2 if (ARGS.dup_lvm and "vl" in model) else 1]
        if self.path == "/api/embed":
            inp = body.get("input")
            inp = [inp] if isinstance(inp, str) else inp
            time.sleep(0.002 * len(inp))
            return self._json(200, {"model": model, "embeddings": [embed(t) for t in inp]})
        if self.path == "/api/generate":
            return self._json(200, {"done": True})
        if self.path == "/api/chat":
            if "think" in body and ARGS.no_think_api:
                return self._json(400, {"error": "registry.ollama.ai/library/qwen3:8b does not support think"})
            msgs = body.get("messages", [])
            system = next((m["content"] for m in msgs if m["role"] == "system"), "")
            user = msgs[-1]["content"] if msgs else ""
            has_img = any(m.get("images") for m in msgs)
            text = answer_for(system, user, has_img)
            think = body.get("think") or user.rstrip().endswith("/think")
            if not body.get("stream", True):
                return self._json(200, {"message": {"role": "assistant", "content": text}, "done": True})
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.end_headers()
            pieces = []
            if think:
                if ARGS.no_think_api:   # old servers emit thinking inline
                    pieces.append({"content": "<think>reasoning about the context...</think>\n"})
                else:
                    pieces += [{"thinking": "Let me check the context. "}, {"thinking": "The answer is there."}]
            toks = re.findall(r"\S+\s*", text) or [text]
            pieces += [{"content": t} for t in toks]
            for p in pieces:
                time.sleep(0.003)
                self.wfile.write((json.dumps({"model": model, "message": {"role": "assistant", **p},
                                              "done": False}, ensure_ascii=False) + "\n").encode())
            n = len(pieces)
            self.wfile.write((json.dumps({"model": model, "message": {"role": "assistant", "content": ""},
                                          "done": True, "done_reason": "stop", "eval_count": n,
                                          "eval_duration": int(n * 0.02e9), "prompt_eval_count": len(user) // 3,
                                          "prompt_eval_duration": int(0.05e9), "load_duration": int(0.1e9),
                                          "total_duration": int(1e9)}) + "\n").encode())
            return
        self._json(404, {"error": "not found"})


def main():
    global ARGS
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=11500)
    ap.add_argument("--no-think-api", action="store_true", help="reject the `think` field like old Ollama")
    ap.add_argument("--fail-every", type=int, default=0, help="return HTTP 500 on every Nth POST")
    ap.add_argument("--unload-delay", type=float, default=1.5, help="seconds until keep_alive=0 takes effect")
    ap.add_argument("--dup-lvm", action="store_true", help="load the vision model as two runners (seen on Ollama 0.40.2)")
    ARGS = ap.parse_args()
    print(f"mock ollama on http://127.0.0.1:{ARGS.port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", ARGS.port), H).serve_forever()


if __name__ == "__main__":
    main()
