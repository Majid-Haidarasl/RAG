#!/usr/bin/env python3
"""Phase 2 environment check: Python, Ollama, required models, GPU.

Usage: python3 experiments/phase-02/check_env.py [--host http://localhost:11434] [--json]
Exit code 0 = ready, 1 = Ollama unreachable, 2 = some model missing (partial run possible).
"""
import argparse
import json
import platform
import shutil
import sys

sys.path.insert(0, __import__("os").path.dirname(__file__))
from common import (DEFAULT_HOST, KIT_VERSION, MODELS, Ollama, OllamaError, model_present,
                    nvidia_smi, setup_utf8)


def collect(host: str) -> dict:
    env = {"kit_version": KIT_VERSION, "python": platform.python_version(),
           "python_ok": sys.version_info >= (3, 9), "platform": platform.platform(),
           "host": host, "ollama": {}, "models": {}, "gpu": nvidia_smi(),
           "ollama_cli": bool(shutil.which("ollama"))}
    try:
        with open("/etc/os-release", encoding="utf-8") as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    env["os"] = line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    cli = Ollama(host, timeout=15, retries=1)
    try:
        env["ollama"]["version"] = cli.version()
        env["ollama"]["reachable"] = True
    except OllamaError as e:
        env["ollama"].update(reachable=False, error=str(e))
        return env
    try:
        tags = cli.tags()
    except OllamaError as e:
        tags = []
        env["ollama"]["tags_error"] = str(e)
    env["ollama"]["installed"] = sorted(m.get("name") for m in tags)
    for role, name in MODELS.items():
        info = {"name": name, "present": model_present(tags, name)}
        if info["present"]:
            for m in tags:
                if m.get("name") in (name, f"{name}:latest"):
                    info["size_gb"] = round(m.get("size", 0) / 1e9, 2)
                    det = m.get("details") or {}
                    info.update(family=det.get("family"), parameter_size=det.get("parameter_size"),
                                quantization=det.get("quantization_level"), format=det.get("format"))
            try:
                sh = cli.show(name)
                mi = sh.get("model_info") or {}
                ctx = [v for k, v in mi.items() if k.endswith(".context_length")]
                emb = [v for k, v in mi.items() if k.endswith(".embedding_length")]
                info["context_length_max"] = ctx[0] if ctx else None
                info["embedding_length"] = emb[0] if emb else None
                info["capabilities"] = sh.get("capabilities")
            except OllamaError as e:
                info["show_error"] = str(e)[:200]
        env["models"][role] = info
    v = env["ollama"].get("version") or "0"
    try:
        major, minor = (int(x) for x in v.split(".")[:2])
        env["ollama"]["think_param_supported"] = (major, minor) >= (0, 9)
    except ValueError:
        env["ollama"]["think_param_supported"] = None
    return env


def print_summary(env: dict) -> int:
    ok = lambda b: "OK " if b else "!! "  # noqa: E731
    print("=" * 60)
    print(f"Phase 2 environment check (kit {env['kit_version']})")
    print("=" * 60)
    print(f"{ok(env['python_ok'])} Python {env['python']}  ({env.get('os', env['platform'])})")
    o = env["ollama"]
    if not o.get("reachable"):
        print(f"!!  Ollama NOT reachable at {env['host']}: {o.get('error')}")
        print("    -> start it:  sudo systemctl start ollama   (or: ollama serve)")
        code = 1
    else:
        print(f"OK  Ollama {o.get('version')} at {env['host']}"
              + ("" if o.get("think_param_supported") else "  (old version: think param via /no_think fallback)"))
        code = 0
        for role, m in env["models"].items():
            if m["present"]:
                print(f"OK  {role:9s} {m['name']:15s} {m.get('parameter_size') or '?':>6s} "
                      f"{m.get('quantization') or '?':8s} {m.get('size_gb')} GB  ctx_max={m.get('context_length_max')}")
            else:
                print(f"!!  {role:9s} {m['name']} MISSING  -> ollama pull {m['name']}")
                code = 2
    g = env["gpu"]
    if isinstance(g, list) and g:
        for x in g:
            print(f"OK  GPU {x['name']}  {x['mem_used_mib']:.0f}/{x['mem_total_mib']:.0f} MiB used  driver {x['driver']}")
    else:
        print(f"!!  GPU info unavailable ({g.get('error') if isinstance(g, dict) else 'none'}); tests still run, VRAM only from /api/ps")
    print("=" * 60)
    print("READY" if code == 0 else ("PARTIAL (missing models will be skipped)" if code == 2 else "NOT READY"))
    return code


def main():
    setup_utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--json", action="store_true", help="print raw JSON too")
    a = ap.parse_args()
    env = collect(a.host)
    code = print_summary(env)
    if a.json:
        print(json.dumps(env, ensure_ascii=False, indent=2))
    sys.exit(code)


if __name__ == "__main__":
    main()
