"""scripts/run_transfer_check.py: offline cycle always, AI suggestions only with (fake) Ollama."""

import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from tests.fixtures.judge.samples import reply
from tests.fixtures.rag.fakes import FakeOllamaServer

pytestmark = [
    pytest.mark.transfer,
    pytest.mark.transfer_pkg,
    pytest.mark.processing,
    pytest.mark.slow,
]

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "run_transfer_check.py"


def run(tmp_path: Path, *args: str) -> tuple[subprocess.CompletedProcess, dict]:
    cmd = [
        sys.executable,
        str(SCRIPT),
        "--out",
        str(tmp_path / "out"),
        "--db",
        str(tmp_path / "db.sqlite"),
        "--exports",
        str(tmp_path / "exports"),
        *args,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900, check=False)
    lines = [
        line for line in proc.stdout.splitlines() if line.startswith("results_json: ")
    ]
    assert lines, proc.stdout[-3000:] + proc.stderr[-3000:]
    return proc, json.loads(
        Path(lines[0].split(": ", 1)[1]).read_text(encoding="utf-8")
    )


def _config(tmp_path: Path, url: str) -> Path:
    cfg = yaml.safe_load((ROOT / "config" / "rag.yaml").read_text(encoding="utf-8"))
    cfg["ollama"]["base_url"] = url
    path = tmp_path / "rag.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return path


def test_offline_cycle_passes(tmp_path: Path) -> None:
    proc, data = run(tmp_path, "--no-live", "--prior", "judge=0")
    assert proc.returncode == 0, proc.stdout[-4000:] + proc.stderr[-2000:]
    assert data["status"] == "PASS"
    assert all(data["checks"].values()), data["checks"]
    assert data["report"]["counts"]["built"] == 19
    assert data["report"]["counts"]["accepted"] == 19
    assert data["store"]["inserted"] == 19
    assert data["rerun"]["second"]["unchanged"] == 19
    assert data["update"]["changed_nodes"] == ["N-CEO", "N-HW", "N-HW-REP"]
    assert data["live"]["status"] == "skipped"
    out = proc.stdout
    assert "======== PHASE 11 SUMMARY ========" in out
    assert "======== END PHASE 11 SUMMARY ========" in out
    assert (tmp_path / "exports" / "1403-Q2" / "latest-packages.csv").is_file()
    board = next(p for p in data["packages"] if p["source_node"] == "N-CEO")
    assert (
        board["detail_level"] == "executive"
        and len({i["issue"]["issue_id"] for i in board["items"]}) <= 3
    )


def test_second_run_stores_nothing_new(tmp_path: Path) -> None:
    run(tmp_path, "--no-live")
    proc, data = run(tmp_path, "--no-live")
    assert data["store"]["unchanged"] == 19 and data["store"]["inserted"] == 0
    assert data["store"]["rows"] == 19
    assert "store: db=" in proc.stdout


def test_failed_prior_step_fails_the_kit(tmp_path: Path) -> None:
    proc, data = run(tmp_path, "--no-live", "--prior", "judge=1", "--pytest-exit", "0")
    assert proc.returncode == 1 and data["status"] == "FAIL"
    assert data["checks"]["prior_steps"] is False


def _fake_reply(messages: list[dict]) -> str:
    system = messages[0]["content"] if messages else ""
    if system.startswith("You advise") or system.startswith("تو به مدیران"):
        return json.dumps(
            {
                "summary": "The package lists the open work.",
                "raise": ["AR-ISS-024/HW"],
                "reason": "It matters.",
            }
        )
    return reply()


def test_live_step_with_fake_ollama(tmp_path: Path) -> None:
    with FakeOllamaServer(models=("qwen3:8b",), chat_reply=_fake_reply) as server:
        proc, data = run(tmp_path, "--config", str(_config(tmp_path, server.url)))
    assert data["live"]["status"] == "ok", data["live"]
    live = data["live"]
    assert live["generated"] == 12 and live["parse_errors"] == 0
    assert len(live["packages"]) == 6 and live["packages"][0] == "N-CEO"
    assert live["templates_llm_accepted"] == 12
    assert "live_suggestions: model=qwen3:8b" in proc.stdout
    assert data["status"] == "PASS"
