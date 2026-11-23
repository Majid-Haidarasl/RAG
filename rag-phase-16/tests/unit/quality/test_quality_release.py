"""Phase 15 quality config, Phase 14 defaults re-check, readiness and scripts/run_quality_check.py."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

from rag_core.quality.application.services import (
    ChoiceCheck,
    choice_checks,
    load_eval_result,
    newest_eval_result,
    readiness,
)
from rag_core.quality.infrastructure.config import load_quality_settings, quality_settings_from_dict
from rag_core.shared_kernel.errors import InvariantError

pytestmark = [pytest.mark.quality]

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "run_quality_check.py"
EXPECTED = {"retrieval": "baseline", "qa_prompt": "qa.answer", "judge_prompt": "strict_precheck",
            "ai_ids": "baseline"}


def test_shipped_quality_config() -> None:
    q = load_quality_settings(ROOT / "config" / "quality.yaml")
    assert q.config_version == "1.0.0" and q.coverage.min_line_pct == 80
    assert q.coverage.report_dir == "results/phase-15" and q.coverage.package == "rag_core"
    assert q.release.tag == "v0.9" and q.release.docs == ("docs/phase-15/unit-test-report.md",
                                                          "docs/phase-15/final-checklist.md")
    assert q.eval.expected == EXPECTED


def test_quality_defaults_when_empty() -> None:
    q = quality_settings_from_dict(None)
    assert q.coverage.min_line_pct == 80.0 and q.release.tag == "v0.9" and q.eval.expected == {}


@pytest.mark.parametrize("data", [
    ["x"],
    {"cover": {}},
    {"coverage": {"min_line": 80}},
    {"coverage": {"min_line_pct": 101}},
    {"release": {"tag": "0.9"}},
    {"eval": {"expected": ["baseline"]}},
])
def test_quality_config_errors(data: object) -> None:
    with pytest.raises(InvariantError):
        quality_settings_from_dict(data)


def payload(agrees: dict[str, object], winners: dict[str, str]) -> dict:
    return {"status": "PASS", "choices": [{"kind": k, "measured": {"winner": winners.get(k)}, "agrees": a}
                                          for k, a in agrees.items()]}


def test_choice_checks() -> None:
    data = payload({"retrieval": True, "qa_prompt": False, "judge_prompt": "yes"}, {"retrieval": "baseline",
                                                                                    "qa_prompt": "qa.answer_complete"})
    rows = {r.kind: r for r in choice_checks(data, EXPECTED, {**EXPECTED, "ai_ids": "listed"})}
    assert rows["retrieval"].confirmed and rows["retrieval"].measured == "baseline"
    assert rows["qa_prompt"].agrees is False and not rows["qa_prompt"].confirmed
    assert rows["judge_prompt"].agrees is None and rows["ai_ids"].measured is None
    assert not rows["ai_ids"].configured_ok and rows["ai_ids"].to_dict()["configured"] == "listed"
    assert [r.measured for r in choice_checks(None, EXPECTED, EXPECTED)] == [None] * 4


def test_newest_and_load_eval_result(tmp_path: Path) -> None:
    assert newest_eval_result(tmp_path / "missing") is None and load_eval_result(None) is None
    for stamp in ("20261123T210037Z", "20261124T080000Z"):
        (tmp_path / f"phase-14-check-{stamp}.json").write_text(json.dumps({"stamp": stamp}), encoding="utf-8")
    (tmp_path / "other.json").write_text("[]", encoding="utf-8")
    newest = newest_eval_result(tmp_path)
    assert newest.name == "phase-14-check-20261124T080000Z.json"
    assert load_eval_result(newest) == {"stamp": "20261124T080000Z"}
    assert load_eval_result(tmp_path / "other.json") is None


def test_readiness() -> None:
    choices = [ChoiceCheck("retrieval", "baseline", "baseline", "baseline", True),
               ChoiceCheck("qa_prompt", "qa.answer", "qa.answer", "x", False),
               ChoiceCheck("ai_ids", "listed_guarded", "listed_guarded", None, None)]
    r = readiness({"pytest": True, "coverage_gate": False}, choices, "ok")
    assert not r.ready and r.blockers == ("coverage_gate",)
    assert r.advisories == ("disagrees:qa_prompt=x", "not_measured:ai_ids")
    live = readiness({"pytest": True}, [], "skipped")
    assert live.ready and live.to_dict() == {"ready": True, "blockers": [], "advisories": ["live:skipped"]}


# ---- the script ----------------------------------------------------------------------------------

def coverage_file(tmp_path: Path, covered: int) -> Path:
    data = {"meta": {"version": "7.6.1", "branch_coverage": True},
            "files": {"src/rag_core/qa/domain/answer.py": {"summary": {"num_statements": 100, "covered_lines": covered,
                                                                       "num_branches": 20, "covered_branches": 15}}}}
    path = tmp_path / "coverage.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def phase14_folder(tmp_path: Path) -> Path:
    folder = tmp_path / "p14"
    folder.mkdir()
    data = payload(dict.fromkeys(EXPECTED, True), EXPECTED)
    data["live"] = {"status": "ok", "judge": {"reports": {}}, "ids": {"summary": {}}}
    (folder / "phase-14-check-20261124T080000Z.json").write_text(json.dumps(data), encoding="utf-8")
    return folder


def run(tmp_path: Path, *args: str) -> tuple[subprocess.CompletedProcess, dict]:
    cmd = [sys.executable, str(SCRIPT), "--out", str(tmp_path / "out"), "--pytest-exit", "0",
           "--prior", "rfp=0,eval=0", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600, check=False)
    lines = [line for line in proc.stdout.splitlines() if line.startswith("results_json: ")]
    assert lines, proc.stdout[-3000:] + proc.stderr[-3000:]
    path = Path(lines[0].split(": ", 1)[1])
    if not path.is_absolute():
        path = ROOT / path
    return proc, json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.slow
def test_script_passes_with_coverage_and_a_phase14_pass(tmp_path: Path) -> None:
    proc, data = run(tmp_path, "--coverage-json", str(coverage_file(tmp_path, 90)), "--coverage-exit", "0",
                     "--phase14-results", str(phase14_folder(tmp_path)))
    out = proc.stdout
    assert proc.returncode == 0, out[-4000:] + proc.stderr[-3000:]
    assert "======== PHASE 15 SUMMARY ========" in out and "status: PASS" in out
    assert "coverage: line=90.0% (90/100) branch=75.0% (15/20) modules=1 gate>=80% ok tool=7.6.1" in out
    assert "checklist: deliverables=80 done=63 external=13 run=3 planned=1 phases=16 problems=0" in out
    assert "precheck_offline: cases=42 " in out and " false_flags=0 " in out
    assert "id_guard: fake listed_retry accepted=0/2 invented=2 listed_guarded accepted=2/2 invented=0" in out
    assert "readiness: ready=yes live_confirmed=4/4" in out
    assert data["status"] == "PASS" and len(data["checks"]) == 11 and all(data["checks"].values())


@pytest.mark.slow
def test_script_fails_without_coverage(tmp_path: Path) -> None:
    proc, data = run(tmp_path, "--coverage-json", str(tmp_path / "none.json"), "--coverage-exit", "skipped",
                     "--phase14-results", str(tmp_path / "no-results"))
    assert proc.returncode == 1 and "status: FAIL" in proc.stdout and "coverage: missing" in proc.stdout
    checks = data["checks"]
    assert not checks["coverage_measured"] and not checks["coverage_gate"] and not checks["phase14_result"]
    assert checks["checklist_complete"] and checks["precheck_offline"] and checks["id_guard"]
