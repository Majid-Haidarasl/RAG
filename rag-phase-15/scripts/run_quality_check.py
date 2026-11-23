#!/usr/bin/env python3
"""Phase 15: unit-test completion, hardening, coverage report and release readiness.

Always (no Ollama needed):
* Reads the coverage report that scripts/setup_and_test.sh wrote with
  pytest-cov / coverage.py (results/phase-15/coverage.json): total line and
  branch coverage of src/rag_core, coverage per bounded context, the least
  covered modules, and the gate of config/quality.yaml (coverage.min_line_pct).
* Counts the tests statically (ast, per folder) next to pytest's numbers.
* Checks the release checklist (config/release-checklist.yaml): every
  deliverable of the 16-phase plan has a status and every "done" path exists.
* Checks the Phase 14 carry-overs: config/eval.yaml selects the measured
  defaults (retrieval=baseline, qa_prompt=qa.answer) and the two new variants
  (strict_precheck, listed_guarded); the fact pre-check on the 42 calibration
  cases (no gold accept flagged, every drop_fact / refuse_answerable flagged);
  the pre-check in front of a fake judge; the invented-id guard with a fake model.
* Reads the newest eval/results/phase-14-check-*.json (written by the Phase 14
  step just before) and prints whether its live step confirmed each default.

The status depends on pytest, the earlier steps and the offline checks only;
the live confirmation is reported as advisory. Prints the PHASE 15 SUMMARY
block and writes results/phase-15/quality-check-<UTC>.json and .md.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from typing import Any

ROOT_CANDIDATE = Path(__file__).resolve().parents[1]
_src = ROOT_CANDIDATE / "src"
if _src.is_dir() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))
_scripts = Path(__file__).resolve().parent
if str(_scripts) not in sys.path:
    sys.path.insert(0, str(_scripts))

from run_project_check import parse_prior, rel  # noqa: E402

from rag_core import __version__  # noqa: E402
from rag_core.judging.application.services import judge_all  # noqa: E402
from rag_core.judging.domain.results import JudgeResult  # noqa: E402
from rag_core.judging.domain.threshold import Decision, PolicyOutcome  # noqa: E402
from rag_core.judging.infrastructure.calibration_json import load_calibration  # noqa: E402
from rag_core.quality.application.services import (  # noqa: E402
    choice_checks,
    load_eval_result,
    newest_eval_result,
    readiness,
)
from rag_core.quality.domain.checklist import by_phase, checklist_problems, phase_status, status_counts  # noqa: E402
from rag_core.quality.domain.coverage import coverage_gate  # noqa: E402
from rag_core.quality.infrastructure.checklist_yaml import load_deliverables  # noqa: E402
from rag_core.quality.infrastructure.config import QualitySettings, load_quality_settings  # noqa: E402
from rag_core.quality.infrastructure.coverage_json import load_coverage_report  # noqa: E402
from rag_core.quality.infrastructure.inventory import count_test_functions, inventory  # noqa: E402
from rag_core.shared_kernel.errors import DomainError  # noqa: E402
from rag_core.tuning.application.precheck import PrecheckedJudge, fact_precheck, precheck_summary  # noqa: E402
from rag_core.tuning.application.services import Generated, IdVariantRunner  # noqa: E402
from rag_core.tuning.domain.required_ids import IdVariant, summarize_id_runs  # noqa: E402
from rag_core.tuning.domain.variants import selection_problems  # noqa: E402
from rag_core.tuning.infrastructure.config import EvalSettings, load_eval_settings  # noqa: E402
from rag_core.tuning.infrastructure.gold_jsonl import load_gold  # noqa: E402
from rag_core.tuning.infrastructure.ids_acl import IdJob  # noqa: E402
from rag_core.tuning.infrastructure.judging_acl import derive_calibration  # noqa: E402

KIT = f"rag-core {__version__} (phase 15 unit-test completion, hardening, coverage, release checklist)"
SEPARATOR_START = "======== PHASE 15 SUMMARY (paste this block) ========"
SEPARATOR_END = "======== END PHASE 15 SUMMARY ========"
LOAD_ERRORS = (DomainError, ValueError, KeyError, TypeError, OSError)
NEW_TEST_FOLDERS = ("hardening", "quality")
CARRYOVER_TESTS = "tuning/test_tuning_carryover.py"


def find_root(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.resolve()
    for cand in (Path.cwd().resolve(), ROOT_CANDIDATE):
        if (cand / "pyproject.toml").is_file() and (cand / "config" / "quality.yaml").is_file():
            return cand
    return ROOT_CANDIDATE


def pct(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f}%"


class AcceptAll:
    """Offline stand-in for the LLM judge: accepts everything it is asked about."""

    name = "fake-accept"

    def __init__(self) -> None:
        self.calls = 0

    def judge(self, case):  # noqa: ANN001, ANN201
        self.calls += 1
        return JudgeResult.for_case(case, self.name, {}, PolicyOutcome(Decision.ACCEPT, 20, 20))


class InventingModel:
    """Offline stand-in for the id guard: the first text names every id plus an invented one, a retry is clean."""

    def __call__(self, job: IdJob, variant: str, note: str) -> Generated:
        text = "; ".join(job.required) + "."
        if note:
            return Generated(text, grounded=True)
        return Generated(text + " AR-ISS-999.", grounded=True, invented=("AR-ISS-999",))


def guard_controls() -> dict[str, Any]:
    jobs = [IdJob("rfp_summary", "AR-RFP-TEST", "fa", ("fact line [AR-ISS-024]",),
                  ("AR-ISS-024", "AR-ISS-024/WEB"), ("AR-ISS-024/WEB",)),
            IdJob("feedback", "PRP-TEST", "en", ("fact line [AR-ISS-024]",), ("PRP-TEST", "AR-ISS-024"), ())]
    runner = IdVariantRunner(InventingModel(), lambda job, text: (True, None))
    rows = runner.run_all(jobs, [IdVariant.LISTED_RETRY.value, IdVariant.LISTED_GUARDED.value])
    summary = summarize_id_runs(rows)
    retry, guarded = summary.get("listed_retry", {}), summary.get("listed_guarded", {})
    ok = retry.get("accepted") == 0 and guarded.get("accepted") == len(jobs) and guarded.get("invented_ids") == 0
    return {"ok": ok, "summary": summary, "jobs": len(jobs)}


def calibration_cases(root: Path, eset: EvalSettings, errors: list[str]) -> tuple[list, dict[str, str]]:
    try:
        base = load_calibration(root / eset.files.calibration)
        derived = derive_calibration(load_gold(root / eset.files.dataset))
    except LOAD_ERRORS as exc:
        errors.append(f"calibration: {type(exc).__name__}: {exc}")
        return [], {}
    mutation = {d.case.case_id: d.mutation for d in derived if d.mutation}
    return [*base, *(d.case for d in derived)], mutation


def metrics_markdown(payload: dict[str, Any]) -> str:
    cov = payload.get("coverage") or {}
    lines = [f"# Phase 15 quality check — {payload['run_at']}", "", f"Status: **{payload['status']}**", "",
             "## Coverage", ""]
    total = cov.get("total") or {}
    lines.append(f"Line coverage {pct(total.get('line_pct'))} ({total.get('covered')}/{total.get('statements')}), "
                 f"branch coverage {pct(total.get('branch_pct'))}, gate >= {cov.get('min_line_pct')}%.")
    lines += ["", "| context | modules | statements | line | branch |", "|---|---|---|---|---|"]
    for ctx, t in (cov.get("contexts") or {}).items():
        lines.append(f"| {ctx} | {t['modules']} | {t['statements']} | {pct(t['line_pct'])} | {pct(t['branch_pct'])} |")
    lines += ["", "Least covered modules:", "", "| module | statements | line |", "|---|---|---|"]
    for m in cov.get("lowest") or []:
        lines.append(f"| {m['path']} | {m['statements']} | {pct(m['line_pct'])} |")
    lines += ["", "## Release checklist", "", "| phase | status | deliverables |", "|---|---|---|"]
    for ph, info in (payload.get("checklist") or {}).get("phases", {}).items():
        lines.append(f"| {ph} | {info['status']} | {info['deliverables']} |")
    lines += ["", "## Phase 14 defaults", "", "| kind | expected | configured | measured | agrees |", "|---|---|---|---|---|"]
    for c in payload.get("choices") or []:
        lines.append(f"| {c['kind']} | {c['expected']} | {c['configured']} | {c['measured'] or '-'} | {c['agrees']} |")
    return "\n".join(lines) + "\n"


def main() -> int:  # noqa: C901 - one linear check script, like the earlier phases
    parser = argparse.ArgumentParser(description="Phase 15 unit-test completion, coverage and release readiness.")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--config", type=Path, default=None, help="config/quality.yaml")
    parser.add_argument("--eval-config", type=Path, default=None, help="config/eval.yaml")
    parser.add_argument("--coverage-json", type=Path, default=None, help="coverage.json (default from quality.yaml)")
    parser.add_argument("--coverage-exit", default=None, help="exit code of `coverage json` or 'skipped'")
    parser.add_argument("--phase14-results", type=Path, default=None, help="folder with phase-14-check-*.json")
    parser.add_argument("--out", type=Path, default=None, help="folder for quality-check-*.json")
    for name in ("passed", "failed", "errors", "skipped", "exit", "line"):
        parser.add_argument(f"--pytest-{name}", default=None)
    parser.add_argument("--python-version", default=None)
    parser.add_argument("--prior", default="", help="earlier steps as name=exit,...")
    args = parser.parse_args()

    root = find_root(args.root)
    qset: QualitySettings = load_quality_settings(args.config or root / "config" / "quality.yaml")
    eset: EvalSettings = load_eval_settings(args.eval_config or root / "config" / "eval.yaml")
    cov_dir = root / qset.coverage.report_dir
    out_dir = args.out or cov_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_json = out_dir / f"quality-check-{stamp}.json"
    out_md = out_dir / f"quality-check-{stamp}.md"
    t0 = time.perf_counter()
    errors: list[str] = []

    # ---- coverage
    cov_path = args.coverage_json or cov_dir / qset.coverage.json_file
    report = None
    try:
        report = load_coverage_report(cov_path, package=qset.coverage.package)
    except LOAD_ERRORS as exc:
        errors.append(f"coverage: {type(exc).__name__}: {exc}")
    gate = coverage_gate(report, qset.coverage.min_line_pct, min_context_pct=qset.coverage.min_context_pct)
    total = report.total if report else None
    contexts = report.by_context() if report else {}
    lowest = report.lowest(qset.coverage.lowest, qset.coverage.min_statements) if report else []

    # ---- tests (static inventory)
    inv = inventory(root / "tests" / "unit")
    inv_by = {r.folder: r for r in inv}
    new_counts = {f: (inv_by[f].functions if f in inv_by else 0) for f in NEW_TEST_FOLDERS}
    carry_path = root / "tests" / "unit" / CARRYOVER_TESTS
    new_counts["carryover"] = count_test_functions(carry_path.read_text(encoding="utf-8"))[0] \
        if carry_path.is_file() else 0

    # ---- release checklist and docs
    items: list = []
    try:
        items = load_deliverables(root / qset.release.checklist)
    except LOAD_ERRORS as exc:
        errors.append(f"checklist: {type(exc).__name__}: {exc}")
    problems = checklist_problems(items, lambda p: (root / p).exists()) if items else []
    counts = status_counts(items)
    phases = {ph: {"status": phase_status(ds), "deliverables": len(ds)} for ph, ds in by_phase(items).items()}
    docs_missing = [d for d in qset.release.docs if not (root / d).is_file()]

    # ---- Phase 14 carry-overs
    configured = {k: s.variant for k, s in eset.selection.items()}
    expected = qset.eval.expected
    defaults_wrong = [f"{k}={configured.get(k, '-')}!={v}" for k, v in expected.items() if configured.get(k) != v]
    sel_problems = selection_problems(eset.selection, eset.known_variants())
    cases, mutation = calibration_cases(root, eset, errors)
    findings = [fact_precheck(c) for c in cases]
    pre = precheck_summary(findings, {c.case_id: c.gold for c in cases}, mutation)
    fake = AcceptAll()
    pj = PrecheckedJudge(fake, name="precheck+fake")
    pj_results = judge_all(pj, cases) if cases else []
    pj_rejects = sum(1 for r in pj_results if not r.accepted)
    by_mut = pre["by_mutation"]

    def all_flagged(kind: str) -> bool:
        v = str(by_mut.get(kind, "0/0")).split("/")
        return v[1] != "0" and v[0] == v[1]

    precheck_ok = (len(cases) == 42 and not pre["false_flags"] and all_flagged("drop_fact")
                   and all_flagged("refuse_answerable") and pj_rejects == pre["flagged"]
                   and fake.calls == len(cases) - pre["flagged"])
    guard = guard_controls()

    # ---- Phase 14 result of this run (live confirmation, advisory)
    p14_path = newest_eval_result(args.phase14_results or root / qset.eval.phase14_results)
    p14: dict[str, Any] | None = None
    try:
        p14 = load_eval_result(p14_path)
    except LOAD_ERRORS as exc:
        errors.append(f"phase14: {type(exc).__name__}: {exc}")
    choices = choice_checks(p14, expected, configured)
    live = (p14 or {}).get("live") or {}
    live_status = str(live.get("status", "missing")) if p14 else "missing"
    judge_reports = (live.get("judge") or {}).get("reports") or {}
    ids_summary = (live.get("ids") or {}).get("summary") or {}

    # ---- checks
    prior = parse_prior(args.prior)
    checks = {
        "pytest": args.pytest_exit in (None, "0", 0),
        "prior_steps": all(v == "0" for v in prior.values()),
        "coverage_measured": report is not None and args.coverage_exit in (None, "0")
        and not any(e.startswith("coverage") for e in errors),
        "coverage_gate": gate.passed,
        "phase15_tests": all(new_counts[f] > 0 for f in (*NEW_TEST_FOLDERS, "carryover")),
        "checklist_complete": bool(items) and not problems,
        "release_docs": not docs_missing,
        "eval_defaults": not defaults_wrong and not sel_problems and bool(expected),
        "precheck_offline": precheck_ok,
        "id_guard": bool(guard["ok"]),
        "phase14_result": p14 is not None and p14.get("status") == "PASS",
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    ready = readiness(checks, choices, live_status)
    total_s = time.perf_counter() - t0

    payload: dict[str, Any] = {
        "kit": KIT,
        "run_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": status,
        "checks": checks,
        "errors": errors,
        "python": args.python_version,
        "pytest": {"passed": args.pytest_passed, "failed": args.pytest_failed, "errors": args.pytest_errors,
                   "skipped": args.pytest_skipped, "exit": args.pytest_exit, "result_line": args.pytest_line},
        "prior_steps": prior,
        "coverage": {"file": rel(root, Path(cov_path)), "exit": args.coverage_exit, "tool": report.tool if report else None,
                     "branch_measured": report.branch_measured if report else False,
                     "total": total.to_dict() if total else None, "min_line_pct": qset.coverage.min_line_pct,
                     "gate": gate.to_dict(), "contexts": {k: v.to_dict() for k, v in contexts.items()},
                     "lowest": [{"path": m.path, "statements": m.statements, "line_pct": m.line_pct,
                                 "branch_pct": m.branch_pct} for m in lowest]},
        "tests": {"folders": [r.__dict__ for r in inv], "phase15": new_counts},
        "checklist": {"deliverables": len(items), "counts": counts, "problems": [str(p) for p in problems],
                      "phases": {str(k): v for k, v in phases.items()}},
        "release": {"tag": qset.release.tag, "title": qset.release.title, "docs_missing": docs_missing,
                    "plan": "tag the pushed Phase 15 commit after this PASS"},
        "eval_defaults": {"configured": configured, "expected": expected, "wrong": defaults_wrong,
                          "selection_problems": sel_problems},
        "precheck": {**pre, "fake_judge_calls": fake.calls, "fake_rejects": pj_rejects,
                     "findings": [f.to_dict() for f in findings if f.applied]},
        "id_guard": guard,
        "phase14": {"file": rel(root, p14_path) if p14_path else None, "status": (p14 or {}).get("status"),
                    "live": live_status, "judge": {k: {kk: v.get(kk) for kk in ("agreement", "by_mutation", "prechecked",
                                                                                  "model_calls")}
                                                   for k, v in judge_reports.items()},
                    "ids": ids_summary},
        "choices": [c.to_dict() for c in choices],
        "readiness": ready.to_dict(),
        "timings": {"total_s": round(total_s, 2)},
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    out_md.write_text(metrics_markdown(payload), encoding="utf-8")

    # ---- summary block
    print()
    print(SEPARATOR_START)
    print(f"status: {status}")
    print(f"kit: {KIT}")
    print(f"python: {args.python_version}")
    for name in ("exit", "passed", "failed", "errors", "skipped"):
        print(f"pytest_{name}: {getattr(args, f'pytest_{name}')}")
    print("prior_steps: " + (" ".join(f"{k}={v}" for k, v in prior.items()) or "none"))
    if errors:
        print("errors: " + " | ".join(errors))
    if total is not None:
        print(f"coverage: line={pct(total.line_pct)} ({total.covered}/{total.statements}) "
              f"branch={pct(total.branch_pct)} ({total.covered_branches}/{total.branches}) modules={total.modules} "
              f"gate>={qset.coverage.min_line_pct:g}% {'ok' if gate.passed else 'FAIL'} tool={report.tool or '-'}")
        print("coverage_contexts: " + " ".join(f"{k}={pct(v.line_pct)}" for k, v in contexts.items()))
        print("coverage_lowest: " + (" ".join(f"{m.path.split('rag_core/')[-1]}={pct(m.line_pct)}" for m in lowest)
                                     or "-"))
    else:
        print(f"coverage: missing ({rel(root, Path(cov_path))}; coverage_exit={args.coverage_exit})")
    print(f"coverage_report: {rel(root, cov_dir)} (coverage.json, coverage.txt, htmlcov/index.html)")
    print(f"tests: folders={len(inv)} files={sum(r.files for r in inv)} functions={sum(r.functions for r in inv)} "
          f"phase15=" + ",".join(f"{k}:{v}" for k, v in new_counts.items()))
    print(f"checklist: deliverables={len(items)} " + " ".join(f"{k}={v}" for k, v in counts.items())
          + f" phases={len(phases)} problems={len(problems)}" + (f" first={problems[0]}" if problems else ""))
    print("checklist_phases: " + " ".join(f"{k}={v['status']}" for k, v in phases.items()))
    print(f"release: tag={qset.release.tag} ({qset.release.title}) not tagged yet; tag the pushed Phase 15 commit "
          f"after this PASS docs={len(qset.release.docs) - len(docs_missing)}/{len(qset.release.docs)}")
    print("eval_defaults: " + " ".join(f"{k}={configured.get(k, '-')}" for k in expected)
          + f" expected={len(expected) - len(defaults_wrong)}/{len(expected)} problems={len(sel_problems)}")
    print(f"precheck_offline: cases={pre['cases']} applied={pre['applied']} flagged={pre['flagged']} "
          f"gold_rejects_flagged={pre['gold_rejects_flagged']}/{pre['gold_rejects']} "
          f"false_flags={len(pre['false_flags'])} by_mutation="
          + ",".join(f"{k}:{v}" for k, v in by_mut.items())
          + f" fake_judge_calls={fake.calls}")
    gs = guard["summary"]
    print("id_guard: fake " + " ".join(f"{k} accepted={v['accepted']}/{v['n']} invented={v['invented_ids']}"
                                       for k, v in gs.items()))
    print(f"phase14_result: {rel(root, p14_path) if p14_path else '-'} status={(p14 or {}).get('status', '-')} "
          f"live={live_status}")
    for key in ("strict", "strict_precheck"):
        r = judge_reports.get(key)
        if r:
            ag = r.get("agreement") or {}
            print(f"live_judge: {key} agreement={ag.get('agree')}/{ag.get('n')} kappa={ag.get('kappa')} "
                  f"false_accepts={ag.get('false_accepts')} false_rejects={ag.get('false_rejects')} by_mutation="
                  + ",".join(f"{k}:{v}" for k, v in (r.get("by_mutation") or {}).items())
                  + (f" prechecked={r['prechecked']}" if r.get("prechecked") is not None else ""))
    for key in ("listed_retry", "listed_guarded"):
        r = ids_summary.get(key)
        if r:
            print(f"live_ids: {key} named={r.get('mentioned')} all_ids={r.get('all_ids')}/{r.get('n')} "
                  f"accepted={r.get('accepted')}/{r.get('n')} invented={r.get('invented_ids')} retries={r.get('retries')}")
    for c in choices:
        print(f"live_confirm: {c.kind} expected={c.expected} configured={c.configured} measured={c.measured or '-'} "
              f"agrees={'-' if c.agrees is None else ('yes' if c.agrees else 'NO')}")
    confirmed = sum(1 for c in choices if c.confirmed)
    print(f"readiness: ready={'yes' if ready.ready else 'no'} live_confirmed={confirmed}/{len(choices)}"
          + (f" advisories={','.join(ready.advisories)}" if ready.advisories else ""))
    print("checks: " + " ".join(f"{k}={'ok' if v else 'FAIL'}" for k, v in checks.items()))
    print(f"results_json: {rel(root, out_json)}")
    print(SEPARATOR_END)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
