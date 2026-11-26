"""scripts/run_judge_check.py: offline checks always, the LLM judge only with Ollama."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from tests.fixtures.judge.samples import reply
from tests.fixtures.rag.fakes import FakeOllamaServer

pytestmark = [pytest.mark.judging, pytest.mark.judge, pytest.mark.slow]

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "run_judge_check.py"

P9_FACTS = [
    "issue AR-ISS-024: Azarpakhsh delivery delay | owner N-LIB | status in_progress | progress 40%",
    ("sub-issue AR-ISS-024/HW: Hardware | owner N-HW-REP | status in_progress | lead Saeed Akbari | "
    "collaborators none | knowledge AR-HW-012 | depends on none | acceptance team_owner:N-HW-REP"),
]


def run(
    tmp_path: Path, *args: str, p8: Path | None = None, p9: Path | None = None
) -> tuple[subprocess.CompletedProcess, dict]:
    empty = tmp_path / "empty"
    empty.mkdir(exist_ok=True)
    cmd = [
        sys.executable,
        str(SCRIPT),
        "--out",
        str(tmp_path / "out"),
        "--phase8-results",
        str(p8 or empty),
        "--phase9-results",
        str(p9 or empty),
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


def _live_results(tmp_path: Path) -> tuple[Path, Path]:
    p8 = tmp_path / "p8"
    p9 = tmp_path / "p9"
    p8.mkdir()
    p9.mkdir()
    answer = {
        "id": "Q01",
        "node": "N-SW-SUP",
        "language": "en",
        "question": "What is the P1 response time?",
        "status": "answered",
        "expected_status": "answered",
        "text": "Within 30 minutes [AR-SW-022 §4].",
        "used_chunks": [{"document_id": "AR-NOPE-001", "language": "en", "order": 1}],
        "citations": [],
    }
    (p8 / "rag-demo-20260101T000000Z.json").write_text(
        json.dumps({"live": {"status": "ok", "answers": [answer]}}), encoding="utf-8"
    )
    summaries = {
        "en": {"text": "AR-ISS-024/HW is in progress and is led by Saeed Akbari."}
    }
    (p9 / "ike-check-20260101T000000Z.json").write_text(
        json.dumps(
            {"live": {"status": "ok", "summaries": summaries, "facts": P9_FACTS}}
        ),
        encoding="utf-8",
    )
    return p8, p9


def test_no_live_passes_and_prints_the_summary(tmp_path: Path) -> None:
    proc, data = run(
        tmp_path,
        "--no-live",
        "--pytest-exit",
        "0",
        "--prior",
        "ingest=0,dedup=0,hierarchy=0,issues=0,rag=0,ike=0",
    )
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-3000:]
    out = proc.stdout
    assert "======== PHASE 10 SUMMARY ========" in out and "status: PASS" in out
    assert "prior_steps: ingest=0 dedup=0 hierarchy=0 issues=0 rag=0 ike=0" in out
    assert "rubric: judge.rubric@1.0.0 out_of=20 accept>=18" in out
    assert "live: skipped (disabled with --no-live)" in out
    assert "phase8_answers_rule: none" in out and "phase9_summaries_rule: none" in out
    assert data["status"] == "PASS" and all(data["checks"].values()), data["checks"]
    assert all(row["ok"] for row in data["parser_cases"])
    cal = data["calibration_rule"]
    assert cal["check"]["agree"] == cal["check"]["n"] == 13 and cal["all"]["n"] == 14
    assert (
        data["negative_controls_rule"]["offline"]["rejected"]
        == data["negative_controls_rule"]["offline"]["n"]
        > 0
    )
    tpl = [
        r for r in data["key_outputs_rule"]["results"] if r["origin"] == "ike-template"
    ]
    assert len(tpl) == 2 and all(r["decision"] == "accept" for r in tpl), tpl


def test_failed_prior_step_fails_status(tmp_path: Path) -> None:
    proc, data = run(tmp_path, "--no-live", "--prior", "ike=1")
    assert (
        proc.returncode == 1
        and data["status"] == "FAIL"
        and data["checks"]["prior_steps"] is False
    )


def test_earlier_live_outputs_are_judged_by_rules(tmp_path: Path) -> None:
    p8, p9 = _live_results(tmp_path)
    proc, data = run(tmp_path, "--no-live", p8=p8, p9=p9)
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-3000:]
    assert (
        data["phase8_results"]["answers"] == 1
        and data["phase8_results"]["missing_chunks"] == 1
    )
    assert data["phase9_results"]["summaries"] == 1
    by_id = {r["case_id"]: r for r in data["key_outputs_rule"]["results"]}
    assert (
        by_id["P8-Q01"]["decision"] == "reject"
    )  # its source chunk is unknown: nothing grounds it
    assert by_id["P9-LLM-en"]["decision"] == "accept", by_id["P9-LLM-en"]
    assert "phase8_answers_rule: file=rag-demo-20260101T000000Z.json" in proc.stdout
    assert (
        "phase9_summaries_rule: file=ike-check-20260101T000000Z.json en=20/20:accept"
        in proc.stdout
    )
    assert data["checks"]["negative_controls_rejected"] is True


def test_missing_model_is_skipped_not_failed(tmp_path: Path) -> None:
    with FakeOllamaServer(models=("bge-m3:latest",)) as srv:
        proc, data = run(tmp_path, "--config", str(_config(tmp_path, srv.url)))
    assert proc.returncode == 0 and data["status"] == "PASS"
    assert data["live"]["status"] == "skipped" and "qwen3:8b" in data["live"]["reason"]


def test_live_judge_against_fake_ollama(tmp_path: Path) -> None:
    with FakeOllamaServer(chat_reply=lambda messages: reply()) as srv:
        proc, data = run(tmp_path, "--config", str(_config(tmp_path, srv.url)))
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-3000:]
    live = data["live"]
    assert live["status"] == "ok", live
    assert live["errors"] == 0 and live["parse_modes"] == {"json": live["cases"]}
    assert live["calibration"]["n"] == 14 and live["key_outputs"]["n"] == 2
    # A judge that accepts everything is caught by the negative controls (reported, not a kit failure).
    assert (
        live["negative_controls"]["n"] > 0
        and live["negative_controls"]["rejected"] == 0
    )
    assert data["status"] == "PASS"
    chats = [body for path, body in srv.requests if path == "/api/chat"]
    assert chats and all(
        b["format"] == "json" and b["options"]["temperature"] == 0.0 for b in chats
    )
    assert "live_judge: llm:qwen3:8b think=off format=json" in proc.stdout
    assert (
        "live_key_outputs:" in proc.stdout and "live_negative_controls:" in proc.stdout
    )
