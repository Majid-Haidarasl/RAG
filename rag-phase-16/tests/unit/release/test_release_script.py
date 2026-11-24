"""scripts/run_release_check.py end to end, with Phase 14 and Phase 15 results in a temp folder."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

pytestmark = [pytest.mark.release]

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "run_release_check.py"
EXPECTED = {
    "retrieval": "baseline",
    "qa_prompt": "qa.answer",
    "judge_prompt": "strict_precheck",
    "ai_ids": "baseline",
}


def results(
    tmp_path: Path, *, p15_status: str = "PASS", agrees: bool = True
) -> tuple[Path, Path]:
    p14, p15 = tmp_path / "p14", tmp_path / "p15"
    p14.mkdir()
    p15.mkdir()
    data = {
        "status": "PASS",
        "live": {"status": "ok"},
        "choices": [
            {"kind": k, "measured": {"winner": v}, "agrees": agrees}
            for k, v in EXPECTED.items()
        ],
    }
    (p14 / "phase-14-check-20261124T080000Z.json").write_text(
        json.dumps(data), encoding="utf-8"
    )
    (p15 / "quality-check-20261124T080500Z.json").write_text(
        json.dumps({"status": p15_status}), encoding="utf-8"
    )
    return p14, p15


def run(tmp_path: Path, *args: str) -> tuple[subprocess.CompletedProcess, dict]:
    cmd = [sys.executable, str(SCRIPT), "--out", str(tmp_path / "out"), *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600, check=False)
    lines = [
        line for line in proc.stdout.splitlines() if line.startswith("results_json: ")
    ]
    assert lines, proc.stdout[-3000:] + proc.stderr[-3000:]
    path = Path(lines[0].split(": ", 1)[1])
    if not path.is_absolute():
        path = ROOT / path
    return proc, json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.slow
def test_script_offline_checks_pass(tmp_path: Path) -> None:
    p14, p15 = results(tmp_path)
    proc, data = run(
        tmp_path,
        "--pytest-exit",
        "0",
        "--prior",
        "eval=0,quality=0",
        "--phase14-results",
        str(p14),
        "--phase15-results",
        str(p15),
    )
    out = proc.stdout
    assert (
        "======== PHASE 16 SUMMARY ========" in out
        and "======== END PHASE 16 SUMMARY ========" in out
    )
    assert "version: 1.0.0 places=7/7" in out
    assert "phrase_scan: " in out and " hits=0" in out
    assert (
        "negative_controls: phrases=11/11 short_doc=caught missing_doc=caught wrong_version=caught "
        "changelog=caught deck=caught"
    ) in out
    assert "changelog: versions=14 newest=1.0.0 problems=0" in out
    assert (
        "checklist: deliverables=80 done=63 external=13 run=3 planned=1 phases=16 problems=0"
        in out
    )
    assert (
        "eval_defaults: retrieval=baseline qa_prompt=qa.answer judge_prompt=strict_precheck ai_ids=baseline "
        "expected=4/4 problems=0"
    ) in out
    assert (
        "live_confirm: ai_ids expected=baseline configured=baseline measured=baseline agrees=yes"
        in out
    )
    assert (
        "live_confirmed=4/4" in out
        and "phase15_result: " in out
        and " status=PASS" in out
    )
    checks = data["checks"]
    assert len(checks) == 12
    offline = (
        "pytest",
        "prior_steps",
        "version_consistent",
        "docs_complete",
        "phrase_scan",
        "negative_controls",
        "changelog",
        "presentation",
        "checklist_complete",
        "eval_defaults",
        "phase15_result",
    )
    assert all(checks[k] for k in offline), {k: checks[k] for k in offline}
    # evidence_present depends on the result files of a full run in this folder
    assert checks["evidence_present"] == all(e["count"] for e in data["evidence"])
    assert data["presentation"]["slides"] >= 10 and data["phrase_scan"]["hits"] == []


@pytest.mark.slow
def test_script_fails_on_earlier_failures(tmp_path: Path) -> None:
    p14, p15 = results(tmp_path, p15_status="FAIL", agrees=False)
    proc, data = run(
        tmp_path,
        "--pytest-exit",
        "1",
        "--prior",
        "eval=0,quality=1",
        "--phase14-results",
        str(p14),
        "--phase15-results",
        str(p15),
    )
    assert proc.returncode == 1 and "status: FAIL" in proc.stdout
    checks = data["checks"]
    assert (
        not checks["pytest"]
        and not checks["prior_steps"]
        and not checks["phase15_result"]
    )
    assert (
        checks["docs_complete"]
        and checks["negative_controls"]
        and checks["eval_defaults"]
    )
    assert (
        "live_confirmed=0/4" in proc.stdout
        and "disagrees:ai_ids=baseline" in proc.stdout
    )


@pytest.mark.slow
def test_script_without_earlier_results(tmp_path: Path) -> None:
    proc, data = run(
        tmp_path,
        "--phase14-results",
        str(tmp_path / "none14"),
        "--phase15-results",
        str(tmp_path / "none15"),
    )
    assert proc.returncode == 1 and "phase15_result: - status=-" in proc.stdout
    assert (
        "readiness: ready=no live_confirmed=0/4" in proc.stdout
        and "live:missing" in proc.stdout
    )
    assert data["phase15"]["file"] is None and data["choices"][0]["measured"] is None
