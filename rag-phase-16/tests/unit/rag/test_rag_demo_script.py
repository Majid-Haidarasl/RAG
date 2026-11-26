"""scripts/run_rag_demo.py: offline check always, live step only with Ollama."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from tests.fixtures.rag.fakes import FakeOllamaServer

pytestmark = [pytest.mark.rag, pytest.mark.slow]

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "run_rag_demo.py"


def run(*args: str) -> tuple[subprocess.CompletedProcess, dict]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    out = Path(
        next(
            line.split(": ", 1)[1]
            for line in proc.stdout.splitlines()
            if line.startswith("results_json: ")
        )
    )
    return proc, json.loads(out.read_text(encoding="utf-8"))


def test_no_live_still_passes_and_reports(tmp_path: Path) -> None:
    proc, data = run(
        "--no-live",
        "--out",
        str(tmp_path),
        "--pytest-exit",
        "0",
        "--prior",
        "ingest=0,dedup=0",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (
        "PHASE 8 SUMMARY" in proc.stdout
        and "status: PASS" in proc.stdout
        and "live: skipped" in proc.stdout
    )
    assert data["status"] == "PASS" and data["live"]["status"] == "skipped"
    assert data["offline"]["checks"]["scope_respected"] is True
    assert data["models"]["generation"] == "qwen3:8b"


def test_failed_prior_step_fails_status(tmp_path: Path) -> None:
    proc, data = run(
        "--no-live", "--out", str(tmp_path), "--pytest-exit", "0", "--prior", "issues=1"
    )
    assert proc.returncode == 1 and data["status"] == "FAIL"


def test_missing_model_is_skipped_not_failed(tmp_path: Path) -> None:
    with FakeOllamaServer(models=("bge-m3:latest",)) as srv:
        cfg = yaml.safe_load((ROOT / "config" / "rag.yaml").read_text(encoding="utf-8"))
        cfg["ollama"]["base_url"] = srv.url
        (tmp_path / "rag.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
        proc, data = run("--config", str(tmp_path / "rag.yaml"), "--out", str(tmp_path))
    assert proc.returncode == 0 and data["live"]["status"] == "skipped"
    assert (
        "qwen3:8b" in data["live"]["reason"] and "ollama pull" in data["live"]["reason"]
    )


def test_live_step_against_fake_ollama(tmp_path: Path) -> None:
    def reply(messages: list[dict]) -> str:
        return (
            "Priority 2: response within 2 hours [AR-SW-022 §1]."
            if "Priority 2" in messages[-1]["content"]
            else "INSUFFICIENT_CONTEXT"
        )

    with FakeOllamaServer(chat_reply=reply) as srv:
        cfg = yaml.safe_load((ROOT / "config" / "rag.yaml").read_text(encoding="utf-8"))
        cfg["ollama"]["base_url"] = srv.url
        cfg["embedding"]["dim"] = 64
        cfg["index"]["path"] = str(tmp_path / "ix.sqlite")
        cfg["qa"]["evidence_min_vector"] = 0.2
        (tmp_path / "rag.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
        proc, data = run("--config", str(tmp_path / "rag.yaml"), "--out", str(tmp_path))
        again, data2 = run(
            "--config", str(tmp_path / "rag.yaml"), "--out", str(tmp_path / "2")
        )
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-3000:]
    live = data["live"]
    assert live["status"] == "ok", live
    assert live["index"]["embedded"] == data["offline"]["corpus"]["active"]
    assert live["qa"]["questions"] == 10 and len(live["answers"]) == 10
    assert "live_qa:" in proc.stdout and "live_index:" in proc.stdout
    assert data2["live"]["index"]["embedded"] == 0, (
        "second run reuses the persistent index"
    )
    assert again.returncode == 0
