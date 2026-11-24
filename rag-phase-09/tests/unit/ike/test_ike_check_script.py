"""scripts/run_ike_check.py: offline checks always, live step only with Ollama."""

import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from tests.fixtures.rag.fakes import FakeOllamaServer

pytestmark = [pytest.mark.ike, pytest.mark.slow]

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "run_ike_check.py"


def run(*args: str) -> tuple[subprocess.CompletedProcess, dict]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=900,
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


def _config(tmp_path: Path, url: str, **overrides: object) -> Path:
    cfg = yaml.safe_load((ROOT / "config" / "rag.yaml").read_text(encoding="utf-8"))
    cfg["ollama"]["base_url"] = url
    for dotted, value in overrides.items():
        section, key = dotted.split("__")
        cfg[section][key] = value
    path = tmp_path / "rag.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return path


def test_no_live_passes_and_reports(tmp_path: Path) -> None:
    proc, data = run(
        "--no-live", "--out", str(tmp_path), "--pytest-exit", "0", "--prior", "rag=0"
    )
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-3000:]
    assert (
        "PHASE 9 SUMMARY" in proc.stdout
        and "status: PASS" in proc.stdout
        and "live: skipped" in proc.stdout
    )
    assert data["status"] == "PASS" and all(data["checks"].values()), data["checks"]
    assert (
        data["executors"]["total"] == 15
        and data["executors"]["capacity_unpublished"] == 3
    )
    assert data["matching"]["roles"]["lead_candidate"] == 5
    assert data["ike"]["registry_graph"]["relations"] == 51
    assert "referral_policy:" in proc.stdout and "(MISMATCH)" not in proc.stdout
    assert data["ike"]["template_summaries"]["fa"]["check"]["grounded"] is True


def test_failed_prior_step_fails_status(tmp_path: Path) -> None:
    proc, data = run("--no-live", "--out", str(tmp_path), "--prior", "issues=1")
    assert (
        proc.returncode == 1
        and data["status"] == "FAIL"
        and data["checks"]["prior_steps"] is False
    )


def test_missing_model_is_skipped_not_failed(tmp_path: Path) -> None:
    with FakeOllamaServer(models=("bge-m3:latest",)) as srv:
        proc, data = run(
            "--config", str(_config(tmp_path, srv.url)), "--out", str(tmp_path)
        )
    assert proc.returncode == 0 and data["live"]["status"] == "skipped"
    assert "qwen3:8b" in data["live"]["reason"]


def test_live_step_against_fake_ollama(tmp_path: Path) -> None:
    def reply(messages: list[dict]) -> str:
        return "<think>hidden</think>AR-ISS-024/HW, AR-ISS-024/WIN, AR-ISS-024/WEB and AR-ISS-024/LEG are tracked."

    with FakeOllamaServer(chat_reply=reply) as srv:
        cfg = _config(
            tmp_path,
            srv.url,
            embedding__dim=64,
            index__path=str(tmp_path / "ix.sqlite"),
        )
        proc, data = run("--config", str(cfg), "--out", str(tmp_path))
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-3000:]
    live = data["live"]
    assert live["status"] == "ok", live
    assert set(live["summaries"]) == {"fa", "en"}
    for summary in live["summaries"].values():
        assert summary["source"] == "llm" and "<think>" not in summary["text"]
        assert (
            summary["check"]["grounded"] is True
            and summary["check"]["coverage"] == "4/4"
        )
    assert live["graph"]["counts"]["part_of"] == 4
    assert "live_summary_fa:" in proc.stdout and "live_knowledge:" in proc.stdout
