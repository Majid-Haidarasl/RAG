"""Shared helpers for the Phase 2 offline-model test kit.

Standard library only. Talks to the local Ollama HTTP API (no internet needed).
"""
from __future__ import annotations

import http.client
import json
import math
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

KIT_VERSION = "0.2.1"
HERE = Path(__file__).resolve().parent            # experiments/phase-02
ROOT = HERE.parent.parent                          # kit root
DATA = HERE / "data"
RESULTS = HERE / "results"
CONFIG = ROOT / "config"

DEFAULT_HOST = os.environ.get("OLLAMA_HOST_URL") or "http://localhost:11434"
MODELS = {
    "embedding": os.environ.get("P2_EMBED_MODEL", "bge-m3:latest"),
    "llm": os.environ.get("P2_LLM_MODEL", "qwen3:8b"),
    "lvm": os.environ.get("P2_LVM_MODEL", "qwen2.5vl:3b"),
}


def setup_utf8() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ---------------------------------------------------------------- text utils
_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_THINK_RE = re.compile(r"<think>.*?</think>", re.S | re.I)


def normalize(text: str) -> str:
    """Normalize FA/EN text for fact matching (digits, separators, ZWNJ, Arabic letters)."""
    if not text:
        return ""
    t = text.translate(_FA_DIGITS)
    t = t.replace("ي", "ی").replace("ك", "ک").replace("ة", "ه").replace("ۀ", "ه")
    t = t.replace("\u200c", " ").replace("\u200f", "").replace("\u200e", "")
    t = t.replace("٫", ".").replace("ـ", "")
    t = re.sub(r"(?<=\d)[٬,،'](?=\d{3}(?!\d))", "", t)  # thousands separators incl. Arabic comma U+060C
    t = re.sub(r"(?<=\d)\s*[٪%]", "%", t)
    t = t.lower()
    t = re.sub(r"[\u064B-\u0652]", "", t)              # Arabic diacritics
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def strip_think(text: str) -> str:
    if not text:
        return ""
    t = _THINK_RE.sub("", text)
    if "</think>" in t:                                   # unterminated opening tag cases
        t = t.split("</think>", 1)[1]
    return t.strip()


def fact_hits(answer: str, fact_groups) -> tuple[int, int, list]:
    """Each group is a list of alternatives; a group is hit if any alternative appears."""
    if not fact_groups:
        return 0, 0, []
    a = normalize(answer)
    missed, hit = [], 0
    for grp in fact_groups:
        if any(normalize(alt) in a for alt in grp):
            hit += 1
        else:
            missed.append(grp[0])
    return hit, len(fact_groups), missed


def extract_json(text: str):
    """Return (obj, error). Accepts raw JSON, fenced JSON or JSON embedded in prose."""
    t = strip_think(text)
    if not t:
        return None, "empty"
    fence = re.search(r"```(?:json)?\s*(.*?)```", t, re.S)
    cands = [t]
    if fence:
        cands.insert(0, fence.group(1))
    for c in cands:
        try:
            return json.loads(c), None
        except Exception:
            pass
    # outermost balanced {...} (or [...]) only. Kit 0.2.1: never fall back to an
    # inner object, which used to count a malformed reply as valid JSON
    # (run 20261109-191910, fa-prompt_only-r1).
    for open_c, close_c in (("{", "}"), ("[", "]")):
        start = t.find(open_c)
        if start == -1:
            continue
        depth, in_str, esc = 0, False, False
        for i in range(start, len(t)):
            ch = t[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == open_c:
                depth += 1
            elif ch == close_c:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(t[start:i + 1]), None
                    except Exception as e:
                        return None, f"malformed-json: {e}"[:160]
        return None, "unterminated-json"
    return None, "no-parsable-json"


# ---------------------------------------------------------------- metrics
def cosine(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def rank_ids(query_vec, index):
    """index: list of (id, vec). Returns ids sorted by cosine desc, with scores."""
    scored = [(cid, cosine(query_vec, v)) for cid, v in index]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def recall_at_k(ranked_ids, relevant, k) -> float:
    return 1.0 if any(r in relevant for r in ranked_ids[:k]) else 0.0


def reciprocal_rank(ranked_ids, relevant) -> float:
    for i, r in enumerate(ranked_ids, 1):
        if r in relevant:
            return 1.0 / i
    return 0.0


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None


def pct(xs, p):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    k = (len(xs) - 1) * p / 100.0
    lo, hi = math.floor(k), math.ceil(k)
    return round(xs[lo] + (xs[hi] - xs[lo]) * (k - lo), 4)


# ---------------------------------------------------------------- data io
def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def write_json(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def append_jsonl(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def load_prompts():
    with open(CONFIG / "prompt-registry.json", encoding="utf-8") as f:
        reg = json.load(f)
    return {p["id"]: p for p in reg["prompts"]}


def render(template: str, **kw) -> str:
    out = template
    for k, v in kw.items():
        out = out.replace("{{" + k + "}}", str(v))
    missing = re.findall(r"\{\{(\w+)\}\}", out)
    if missing:
        raise ValueError(f"unfilled prompt variables: {missing}")
    return out


# ---------------------------------------------------------------- Ollama client
class OllamaError(RuntimeError):
    pass


class Ollama:
    def __init__(self, host: str = DEFAULT_HOST, timeout: float = 300, retries: int = 2):
        self.host = host.rstrip("/")
        self.timeout = timeout
        self.retries = retries

    # -- low level
    def _req(self, method, path, payload=None, timeout=None, stream=False):
        url = self.host + path
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        return urllib.request.urlopen(req, timeout=timeout or self.timeout)

    def _call(self, method, path, payload=None, timeout=None):
        last = None
        for attempt in range(self.retries + 1):
            try:
                with self._req(method, path, payload, timeout) as r:
                    body = r.read().decode("utf-8")
                    return json.loads(body) if body.strip() else {}
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:500]
                if e.code in (400, 404):                  # not retryable
                    raise OllamaError(f"HTTP {e.code} {path}: {detail}") from None
                last = OllamaError(f"HTTP {e.code} {path}: {detail}")
            except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError,
                    http.client.HTTPException, json.JSONDecodeError) as e:
                last = OllamaError(f"{path}: {type(e).__name__}: {e}")
            if attempt < self.retries:
                time.sleep(2 * (attempt + 1))
        raise last

    # -- endpoints
    def version(self):
        return self._call("GET", "/api/version", timeout=5).get("version")

    def tags(self):
        return self._call("GET", "/api/tags", timeout=10).get("models", [])

    def ps(self):
        try:
            return self._call("GET", "/api/ps", timeout=10).get("models", [])
        except OllamaError:
            return []

    def show(self, model):
        return self._call("POST", "/api/show", {"model": model}, timeout=30)

    def embed(self, model, texts, keep_alive="10m", num_ctx=8192):
        t0 = time.perf_counter()
        r = self._call("POST", "/api/embed", {"model": model, "input": texts, "keep_alive": keep_alive,
                                              "options": {"num_ctx": num_ctx}})
        return r.get("embeddings", []), time.perf_counter() - t0, r

    def _unload_request(self, model):
        try:
            if "embed" in model or "bge" in model:
                self._call("POST", "/api/embed", {"model": model, "input": "x", "keep_alive": 0}, timeout=30)
            else:
                self._call("POST", "/api/generate", {"model": model, "keep_alive": 0}, timeout=30)
        except OllamaError:
            pass

    def loaded(self):
        return [m.get("name") for m in self.ps()]

    def unload(self, model, wait_s=30.0):
        """Unload and VERIFY via /api/ps. Ollama unloads asynchronously and may keep more than one
        runner of the same model, so the request is repeated until no instance is listed.
        Returns True if the model is gone within wait_s."""
        t0 = time.time()
        while time.time() - t0 < wait_s:
            if model not in self.loaded():
                return True
            self._unload_request(model)
            time.sleep(1.0)
        return model not in self.loaded()

    def unload_all(self, keep=(), wait_s=45.0):
        """Unload every loaded model except `keep`; returns list of models that could not be unloaded."""
        stuck = []
        for name in sorted(set(self.loaded()) - set(keep)):
            if not self.unload(name, wait_s=wait_s):
                stuck.append(name)
        return stuck

    def chat(self, model, messages, think=None, fmt=None, options=None, keep_alive="10m", timeout=None):
        """Streaming chat. Returns dict with content, thinking, timings and Ollama counters.

        think: True/False/None. If the server rejects the `think` field (old Ollama),
        falls back to the qwen3 soft switch (/think or /no_think appended to the last user turn).
        """
        payload = {"model": model, "messages": messages, "stream": True, "keep_alive": keep_alive,
                   "options": options or {}}
        if fmt is not None:
            payload["format"] = fmt
        think_mode = "none"
        if think is not None:
            payload["think"] = bool(think)
            think_mode = "api"
        last_err = None
        for attempt in range(self.retries + 1):
            try:
                res = self._stream_chat(payload, timeout)
                res["think_mode"] = think_mode
                return res
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:300]
                if e.code == 400 and "think" in payload and "think" in detail.lower():
                    payload = dict(payload)
                    payload.pop("think")
                    msgs = [dict(m) for m in payload["messages"]]
                    msgs[-1]["content"] += "\n/think" if think else "\n/no_think"
                    payload["messages"] = msgs
                    think_mode = "soft-switch"
                    continue
                if e.code in (400, 404):
                    raise OllamaError(f"HTTP {e.code} /api/chat: {detail}") from None
                last_err = OllamaError(f"HTTP {e.code} /api/chat: {detail}")
            except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError,
                    http.client.HTTPException, json.JSONDecodeError) as e:
                last_err = OllamaError(f"/api/chat: {type(e).__name__}: {e}")
            if attempt < self.retries:
                time.sleep(2 * (attempt + 1))
        raise last_err or OllamaError("chat failed")

    def _stream_chat(self, payload, timeout):
        t0 = time.perf_counter()
        first_any = first_content = None
        content, thinking, final = [], [], {}
        inline_think = False   # old servers / soft switch put <think>...</think> inside content
        with self._req("POST", "/api/chat", payload, timeout=timeout or self.timeout) as r:
            for raw in r:
                line = raw.decode("utf-8").strip()
                if not line:
                    continue
                obj = json.loads(line)
                if obj.get("error"):
                    raise OllamaError(obj["error"])
                msg = obj.get("message") or {}
                c, th = msg.get("content") or "", msg.get("thinking") or ""
                now = time.perf_counter() - t0
                if (c or th) and first_any is None:
                    first_any = now
                if c and not content and c.lstrip().startswith("<think>"):
                    inline_think = True
                if c and first_content is None:
                    if not inline_think:
                        first_content = now
                    elif "</think>" in "".join(content) + c:
                        tail = ("".join(content) + c).split("</think>", 1)[1]
                        if tail.strip():
                            first_content = now
                if c:
                    content.append(c)
                if th:
                    thinking.append(th)
                if obj.get("done"):
                    final = obj
                    break
        wall = time.perf_counter() - t0
        raw_content = "".join(content)
        think_text = "".join(thinking)
        m = re.search(r"<think>(.*?)</think>", raw_content, re.S)
        if m and not think_text:
            think_text = m.group(1)
        ev_n, ev_d = final.get("eval_count"), final.get("eval_duration")
        pe_n, pe_d = final.get("prompt_eval_count"), final.get("prompt_eval_duration")
        return {
            "content": strip_think(raw_content),
            "raw_content": raw_content,
            "thinking": think_text,
            "thinking_chars": len(think_text),
            "wall_s": round(wall, 3),
            "ttft_s": round(first_any, 3) if first_any is not None else None,
            "ttfc_s": round(first_content, 3) if first_content is not None else None,
            "eval_count": ev_n,
            "prompt_eval_count": pe_n,
            "tokens_per_s": round(ev_n / (ev_d / 1e9), 2) if ev_n and ev_d else None,
            "prompt_tokens_per_s": round(pe_n / (pe_d / 1e9), 2) if pe_n and pe_d else None,
            "load_s": round(final.get("load_duration", 0) / 1e9, 3) if final.get("load_duration") else None,
            "done_reason": final.get("done_reason"),
        }


# ---------------------------------------------------------------- GPU
def nvidia_smi():
    """Return list of GPU dicts or {'error': ...}."""
    q = "name,memory.total,memory.used,utilization.gpu,driver_version,temperature.gpu"
    try:
        out = subprocess.run(["nvidia-smi", f"--query-gpu={q}", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10)
    except FileNotFoundError:
        return {"error": "nvidia-smi not found"}
    except Exception as e:  # noqa
        return {"error": str(e)}
    if out.returncode != 0:
        return {"error": out.stderr.strip()[:200]}
    gpus = []
    for line in out.stdout.strip().splitlines():
        p = [x.strip() for x in line.split(",")]
        if len(p) >= 6:
            gpus.append({"name": p[0], "mem_total_mib": _num(p[1]), "mem_used_mib": _num(p[2]),
                         "util_pct": _num(p[3]), "driver": p[4], "temp_c": _num(p[5])})
    return gpus


def _num(x):
    try:
        return float(x)
    except Exception:
        return None


def vram_snapshot(client: Ollama, label: str, settle_s: float = 0.0) -> dict:
    if settle_s:
        time.sleep(settle_s)          # let freed CUDA memory show up in nvidia-smi
    ps = client.ps()
    names = [m.get("name") for m in ps]
    return {
        "duplicates": sorted({n for n in names if names.count(n) > 1}),
        "partially_offloaded": [m.get("name") for m in ps if m.get("size_vram", 0) < m.get("size", 0)],
        "label": label,
        "time": time.strftime("%H:%M:%S"),
        "ollama_ps": [{"name": m.get("name"), "size_mb": round(m.get("size", 0) / 2**20),
                       "size_vram_mb": round(m.get("size_vram", 0) / 2**20),
                       "context_length": m.get("context_length")} for m in ps],
        "nvidia_smi": nvidia_smi(),
    }


def model_present(tags, name):
    names = {m.get("name") for m in tags} | {m.get("model") for m in tags}
    if name in names:
        return True
    if ":" not in name and f"{name}:latest" in names:
        return True
    return False
