#!/usr/bin/env python3
"""Phase 16: release check of rag-core 1.0.0.

Always offline (no Ollama needed), driven by config/release.yaml:
* every place that carries the kit version agrees (pyproject, package, configs);
* the release documents exist, are long enough and contain their key lines;
* no text left over from drafting ships in the kit (phrase scan of every text file);
* negative controls: planted phrases, a short and a missing document, a wrong version,
  a changelog without the newest entry and a too-short deck are all caught;
* CHANGELOG.md lists every version from 0.3.0 to 1.0.0, newest first;
* the slide deck is a real .pptx with 10-12 slides and its source is in the kit;
* the result files of this run exist for every phase (evidence index);
* the release checklist has no problems and only the v1.0 tag is still planned;
* config/eval.yaml selects the four measured defaults (ai_ids=baseline);
* the newest Phase 15 quality check of this run passed.

The live confirmation of the four defaults comes from the newest Phase 14 result and is
reported next to the status (advisory, like in Phase 15). Prints the PHASE 16 SUMMARY block
and writes results/phase-16/release-check-<UTC>.json and .md.
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
from rag_core.quality.application.services import (  # noqa: E402
    choice_checks,
    load_eval_result,
    newest_eval_result,
    readiness,
)
from rag_core.quality.domain.checklist import by_phase, checklist_problems, phase_status, status_counts  # noqa: E402
from rag_core.quality.domain.release import (  # noqa: E402
    DocRequirement,
    changelog_problems,
    changelog_versions,
    check_doc,
    presentation_problems,
    scan_texts,
    slide_count,
    version_problems,
)
from rag_core.quality.infrastructure.checklist_yaml import load_deliverables  # noqa: E402
from rag_core.quality.infrastructure.release_config import ReleaseCheckSettings, load_release_settings  # noqa: E402
from rag_core.quality.infrastructure.release_files import (  # noqa: E402
    evidence_matches,
    kit_texts,
    read_text,
    version_in,
    zip_names,
)
from rag_core.shared_kernel.errors import DomainError  # noqa: E402
from rag_core.tuning.domain.variants import selection_problems  # noqa: E402
from rag_core.tuning.infrastructure.config import EvalSettings, load_eval_settings  # noqa: E402

KIT = f"rag-core {__version__} (phase 16 release: documents, presentation, training, final checks)"
SEPARATOR_START = "======== PHASE 16 SUMMARY ========"
SEPARATOR_END = "======== END PHASE 16 SUMMARY ========"
LOAD_ERRORS = (DomainError, ValueError, KeyError, TypeError, OSError)
CHECKLIST = "config/release-checklist.yaml"


def find_root(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.resolve()
    for cand in (Path.cwd().resolve(), ROOT_CANDIDATE):
        if (cand / "pyproject.toml").is_file() and (cand / "config" / "release.yaml").is_file():
            return cand
    return ROOT_CANDIDATE


def negative_controls(rset: ReleaseCheckSettings, found_versions: dict[str, str | None]) -> dict[str, Any]:
    """Each control plants one known fault; the check must catch every one."""
    phrases = list(rset.scan.phrases)
    planted = [(f"planted/{i}.md", f"# Notes\n\nfirst line\nsee {p.upper()} below\n") for i, p in enumerate(phrases)]
    hits = scan_texts(planted, phrases)
    caught_phrases = len({h.path for h in hits})
    req = rset.docs[0] if rset.docs else DocRequirement("README.md", 400, ("x",))
    short_doc = not check_doc(req, "# Title\n").ok
    missing_doc = not check_doc(req, None).ok
    wrong_version = bool(version_problems(rset.version, {**found_versions, "planted": "0.0.1"}))
    old_log = "# Changelog\n\n## [0.15.0]\n- quality\n"
    changelog = bool(changelog_problems(old_log, rset.changelog.versions, rset.version))
    few = ["[Content_Types].xml", "ppt/presentation.xml", "ppt/slides/slide1.xml"]
    deck = bool(presentation_problems(few, rset.presentation.min_slides, rset.presentation.max_slides))
    ok = (bool(phrases) and caught_phrases == len(phrases) and short_doc and missing_doc and wrong_version
          and changelog and deck)
    return {"ok": ok, "phrases": f"{caught_phrases}/{len(phrases)}", "short_doc": short_doc,
            "missing_doc": missing_doc, "wrong_version": wrong_version, "changelog": changelog, "deck": deck}


def report_markdown(payload: dict[str, Any]) -> str:
    lines = [f"# Phase 16 release check — {payload['run_at']}", "", f"Status: **{payload['status']}**", "",
             "| Check | Result |", "|---|---|"]
    lines += [f"| {k} | {'ok' if v else 'FAIL'} |" for k, v in payload["checks"].items()]
    lines += ["", "## Documents", "", "| File | Result |", "|---|---|"]
    lines += [f"| `{d['path']}` | {d['reason']} |" for d in payload["docs"]]
    lines += ["", "## Evidence", "", "| Step | Files | Newest |", "|---|---|---|"]
    lines += [f"| {e['name']} | {e['count']} | `{e['newest'] or '-'}` |" for e in payload["evidence"]]
    lines += ["", "## Evaluation defaults", "", "| Kind | Expected | Configured | Measured | Agrees |",
              "|---|---|---|---|---|"]
    lines += [f"| {c['kind']} | {c['expected']} | {c['configured']} | {c['measured'] or '-'} | "
              f"{'-' if c['agrees'] is None else ('yes' if c['agrees'] else 'no')} |" for c in payload["choices"]]
    return "\n".join(lines) + "\n"


def main() -> int:  # noqa: C901 - one linear check script, like the earlier phases
    parser = argparse.ArgumentParser(description="Phase 16 release check.")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--config", type=Path, default=None, help="config/release.yaml")
    parser.add_argument("--eval-config", type=Path, default=None, help="config/eval.yaml")
    parser.add_argument("--phase14-results", type=Path, default=None, help="folder with phase-14-check-*.json")
    parser.add_argument("--phase15-results", type=Path, default=None, help="folder with quality-check-*.json")
    parser.add_argument("--out", type=Path, default=None, help="folder for release-check-*.json")
    for name in ("passed", "failed", "errors", "skipped", "exit", "line"):
        parser.add_argument(f"--pytest-{name}", default=None)
    parser.add_argument("--python-version", default=None)
    parser.add_argument("--prior", default="", help="earlier steps as name=exit,...")
    args = parser.parse_args()

    root = find_root(args.root)
    rset = load_release_settings(args.config or root / "config" / "release.yaml")
    eset: EvalSettings = load_eval_settings(args.eval_config or root / "config" / "eval.yaml")
    out_dir = args.out or root / "results" / "phase-16"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_json = out_dir / f"release-check-{stamp}.json"
    out_md = out_dir / f"release-check-{stamp}.md"
    t0 = time.perf_counter()
    errors: list[str] = []

    # ---- versions
    found_versions: dict[str, str | None] = {}
    for where, how in rset.versions.items():
        try:
            found_versions[where] = version_in(root, where, how)
        except LOAD_ERRORS as exc:
            errors.append(f"version {where}: {type(exc).__name__}: {exc}")
            found_versions[where] = None
    found_versions["rag_core.__version__"] = __version__
    wrong_versions = version_problems(rset.version, found_versions)

    # ---- documents, phrase scan, changelog, slides
    docs = [check_doc(req, read_text(root, req.path)) for req in rset.docs]
    bad_docs = [d for d in docs if not d.ok]
    texts = list(kit_texts(root, rset.scan.suffixes, rset.scan.exclude))
    hits = scan_texts(texts, rset.scan.phrases) if rset.scan.phrases else []
    log_text = read_text(root, rset.changelog.path)
    log_versions = changelog_versions(log_text or "")
    log_problems = (changelog_problems(log_text, rset.changelog.versions, rset.version)
                    if log_text is not None else ["missing"])
    names = zip_names(root / rset.presentation.path)
    deck_problems = presentation_problems(names, rset.presentation.min_slides, rset.presentation.max_slides)
    source_ok = (root / rset.presentation.source).is_file()
    controls = negative_controls(rset, found_versions)

    # ---- evidence of this run
    evidence = []
    for item in rset.evidence:
        files = evidence_matches(root, item.pattern)
        evidence.append({"name": item.name, "pattern": item.pattern, "count": len(files),
                         "newest": files[-1] if files else None})
    evidence_missing = [e["name"] for e in evidence if not e["count"]]

    # ---- checklist
    items: list = []
    try:
        items = load_deliverables(root / CHECKLIST)
    except LOAD_ERRORS as exc:
        errors.append(f"checklist: {type(exc).__name__}: {exc}")
    problems = checklist_problems(items, lambda p: (root / p).exists()) if items else []
    counts = status_counts(items)
    phases = {ph: phase_status(ds) for ph, ds in by_phase(items).items()}
    planned = [d.spec for d in items if d.status == "planned"]
    planned_other = [s for s in planned if rset.tag not in s]

    # ---- evaluation defaults and the earlier results of this run
    configured = {k: s.variant for k, s in eset.selection.items()}
    expected = rset.eval_expected
    defaults_wrong = [f"{k}={configured.get(k, '-')}!={v}" for k, v in expected.items() if configured.get(k) != v]
    sel_problems = selection_problems(eset.selection, eset.known_variants())
    p15_path = newest_eval_result(args.phase15_results or root / "results" / "phase-15", "quality-check-*.json")
    p14_path = newest_eval_result(args.phase14_results or root / eset.files.results_dir)
    p15: dict[str, Any] | None = None
    p14: dict[str, Any] | None = None
    try:
        p15 = load_eval_result(p15_path)
        p14 = load_eval_result(p14_path)
    except LOAD_ERRORS as exc:
        errors.append(f"results: {type(exc).__name__}: {exc}")
    choices = choice_checks(p14, expected, configured)
    live_status = str(((p14 or {}).get("live") or {}).get("status", "missing")) if p14 else "missing"

    # ---- checks
    prior = parse_prior(args.prior)
    checks = {
        "pytest": args.pytest_exit in (None, "0", 0),
        "prior_steps": all(v == "0" for v in prior.values()),
        "version_consistent": not wrong_versions and not any(e.startswith("version") for e in errors),
        "docs_complete": bool(docs) and not bad_docs,
        "phrase_scan": bool(rset.scan.phrases) and bool(texts) and not hits,
        "negative_controls": bool(controls["ok"]),
        "changelog": not log_problems,
        "presentation": not deck_problems and source_ok,
        "evidence_present": bool(evidence) and not evidence_missing,
        "checklist_complete": bool(items) and not problems and not planned_other,
        "eval_defaults": bool(expected) and not defaults_wrong and not sel_problems,
        "phase15_result": p15 is not None and p15.get("status") == "PASS",
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    ready = readiness(checks, choices, live_status)
    confirmed = sum(1 for c in choices if c.confirmed)
    slides = slide_count(names or [])

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
        "version": {"expected": rset.version, "found": found_versions, "wrong": wrong_versions},
        "docs": [{"path": d.path, "ok": d.ok, "chars": d.chars, "reason": d.reason} for d in docs],
        "phrase_scan": {"files": len(texts), "phrases": len(rset.scan.phrases), "hits": [str(h) for h in hits]},
        "negative_controls": controls,
        "changelog": {"versions": log_versions, "problems": log_problems},
        "presentation": {"path": rset.presentation.path, "slides": slides, "source": source_ok,
                         "problems": deck_problems},
        "evidence": evidence,
        "checklist": {"deliverables": len(items), "counts": counts, "problems": [str(p) for p in problems],
                      "phases": {str(k): v for k, v in phases.items()}, "planned": planned},
        "eval_defaults": {"configured": configured, "expected": expected, "wrong": defaults_wrong,
                          "selection_problems": sel_problems},
        "phase15": {"file": rel(root, p15_path) if p15_path else None, "status": (p15 or {}).get("status")},
        "phase14": {"file": rel(root, p14_path) if p14_path else None, "status": (p14 or {}).get("status"),
                    "live": live_status},
        "choices": [c.to_dict() for c in choices],
        "readiness": ready.to_dict(),
        "release": {"tag": rset.tag, "title": rset.title, "plan": "set on the pushed Phase 16 commit"},
        "timings": {"total_s": round(time.perf_counter() - t0, 2)},
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    out_md.write_text(report_markdown(payload), encoding="utf-8")

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
    print(f"version: {rset.version} places={len(found_versions) - len(wrong_versions)}/{len(found_versions)}"
          + (f" wrong={','.join(wrong_versions)}" if wrong_versions else ""))
    print(f"docs: complete={len(docs) - len(bad_docs)}/{len(docs)}"
          + (" problems=" + ",".join(f"{d.path}:{d.reason}" for d in bad_docs[:5]) if bad_docs else ""))
    print(f"phrase_scan: files={len(texts)} phrases={len(rset.scan.phrases)} hits={len(hits)}"
          + (" first=" + ",".join(str(h) for h in hits[:3]) if hits else ""))
    print(f"negative_controls: phrases={controls['phrases']} short_doc={'caught' if controls['short_doc'] else 'MISSED'} "
          f"missing_doc={'caught' if controls['missing_doc'] else 'MISSED'} "
          f"wrong_version={'caught' if controls['wrong_version'] else 'MISSED'} "
          f"changelog={'caught' if controls['changelog'] else 'MISSED'} deck={'caught' if controls['deck'] else 'MISSED'}")
    print(f"changelog: versions={len(log_versions)} newest={log_versions[0] if log_versions else '-'} "
          f"problems={len(log_problems)}" + (f" first={log_problems[0]}" if log_problems else ""))
    print(f"presentation: {rset.presentation.path} slides={slides} source={'yes' if source_ok else 'no'} "
          f"problems={len(deck_problems)}" + (f" first={deck_problems[0]}" if deck_problems else ""))
    print(f"evidence: present={len(evidence) - len(evidence_missing)}/{len(evidence)}"
          + (f" missing={','.join(evidence_missing)}" if evidence_missing else ""))
    print(f"checklist: deliverables={len(items)} " + " ".join(f"{k}={v}" for k, v in counts.items())
          + f" phases={len(phases)} problems={len(problems)}" + (f" first={problems[0]}" if problems else ""))
    print("checklist_phases: " + " ".join(f"{k}={v}" for k, v in phases.items()))
    print("eval_defaults: " + " ".join(f"{k}={configured.get(k, '-')}" for k in expected)
          + f" expected={len(expected) - len(defaults_wrong)}/{len(expected)} problems={len(sel_problems)}")
    print(f"phase15_result: {rel(root, p15_path) if p15_path else '-'} status={(p15 or {}).get('status', '-')}")
    print(f"phase14_result: {rel(root, p14_path) if p14_path else '-'} status={(p14 or {}).get('status', '-')} "
          f"live={live_status}")
    for c in choices:
        print(f"live_confirm: {c.kind} expected={c.expected} configured={c.configured} measured={c.measured or '-'} "
              f"agrees={'-' if c.agrees is None else ('yes' if c.agrees else 'NO')}")
    print(f"readiness: ready={'yes' if ready.ready else 'no'} live_confirmed={confirmed}/{len(choices)}"
          + (f" advisories={','.join(ready.advisories)}" if ready.advisories else ""))
    print(f"release: tag={rset.tag} ({rset.title}) on the pushed Phase 16 commit after a PASS")
    print("checks: " + " ".join(f"{k}={'ok' if v else 'FAIL'}" for k, v in checks.items()))
    print(f"results_json: {rel(root, out_json)}")
    print(SEPARATOR_END)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
