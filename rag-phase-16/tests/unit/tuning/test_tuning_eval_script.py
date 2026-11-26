"""scripts/run_eval_check.py: the offline checks always; the live step only with Ollama."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.tuning, pytest.mark.slow]

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "run_eval_check.py"


def run(tmp_path: Path, *args: str) -> tuple[subprocess.CompletedProcess, dict]:
    cmd = [sys.executable, str(SCRIPT), "--out", str(tmp_path / "out"), *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900, check=False)
    lines = [
        line for line in proc.stdout.splitlines() if line.startswith("results_json: ")
    ]
    assert lines, proc.stdout[-3000:] + proc.stderr[-3000:]
    path = Path(lines[0].split(": ", 1)[1])
    if not path.is_absolute():
        path = ROOT / path
    return proc, json.loads(path.read_text(encoding="utf-8"))


def test_no_live_passes_and_prints_the_summary(tmp_path: Path) -> None:
    proc, data = run(
        tmp_path, "--no-live", "--pytest-exit", "0", "--prior", "projects=0,rfp=0"
    )
    out = proc.stdout
    assert proc.returncode == 0, out[-4000:] + proc.stderr[-3000:]
    assert "======== PHASE 14 SUMMARY ========" in out and "status: PASS" in out
    assert "prior_steps: projects=0 rfp=0" in out
    assert (
        "gold: items=32 pairs=16 fa=16 en=16 answered=28 refusals=4 phase8=10/10 new_pairs=6 problems=0"
        in out
    )
    assert "calibration: base=14 derived=28 total=42" in out
    assert "live: skipped (disabled with --no-live)" in out
    assert out.count("retrieval_offline: ") == 4 and "q06_offline: " in out
    assert data["status"] == "PASS" and all(data["checks"].values()), data["checks"]
    assert len(data["checks"]) == 12
    assert (
        data["calibration"]["derived_accepts"] == "14/14"
        and data["calibration"]["derived_rejects"] == "14/14"
    )
    assert {c["kind"] for c in data["choices"]} == {
        "retrieval",
        "qa_prompt",
        "judge_prompt",
        "ai_ids",
    }
    md = sorted((tmp_path / "out").glob("updated-metrics-*.md"))
    assert md and "| baseline |" in md[0].read_text(encoding="utf-8")


def test_unreachable_ollama_is_skipped(tmp_path: Path) -> None:
    cfg = yaml.safe_load((ROOT / "config" / "rag.yaml").read_text(encoding="utf-8"))
    cfg["ollama"]["base_url"] = "http://127.0.0.1:9"
    cfg["ollama"]["connect_timeout_s"] = 1
    cfg["ollama"]["retries"] = 0
    path = tmp_path / "rag.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    proc, data = run(tmp_path, "--config", str(path), "--pytest-exit", "0")
    assert proc.returncode == 0, proc.stdout[-3000:]
    assert (
        data["live"]["status"] == "skipped"
        and "not reachable" in data["live"]["reason"]
    )
    assert "live: skipped (Ollama not reachable" in proc.stdout
