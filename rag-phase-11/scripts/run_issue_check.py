#!/usr/bin/env python3
"""Phase 7: issue & sub-issue registry check.

* Loads the Phase 6 hierarchy registry through the issues ACL
  (``HierarchyOrgDirectory``) and the seed issue registry
  ``data/issues/issue-registry.json``; validates both.
* Reports issue / sub-issue counts per status and status category, the
  relative position (layer, depth, local / cross-unit, escalation target).
* Re-decomposes the Azarpakhsh issue (AR-ISS-024) with the rule-based
  decomposer and checks it against the seeded sub-issues.
* Compares the sample new issues (``data/issues/new-issue-samples.json``)
  with the registry and checks the expected duplicate / related / new labels.
* Exercises the closure invariants on an in-memory copy.
* Prints the ``PHASE 7 SUMMARY`` block (with pytest counts and PASS/FAIL) and
  writes ``results/phase-07/issue-check-<UTC>.json``.
"""

from __future__ import annotations

import argparse
from collections import Counter
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT_CANDIDATE = Path(__file__).resolve().parents[1]
_src = ROOT_CANDIDATE / "src"
if _src.is_dir() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from rag_core import __version__  # noqa: E402
from rag_core.issues.application.services import load_issue_registry  # noqa: E402
from rag_core.issues.domain.comparison import (  # noqa: E402
    DUPLICATE_MIN_TEXT,
    DUPLICATE_SCORE,
    RELATED_SCORE,
    IssueComparator,
)
from rag_core.issues.domain.decomposition import RuleBasedDecomposer  # noqa: E402
from rag_core.issues.domain.status import IssueStatus  # noqa: E402
from rag_core.issues.infrastructure.hierarchy_acl import HierarchyOrgDirectory  # noqa: E402
from rag_core.issues.infrastructure.registry_json import issue_from_sample  # noqa: E402
from rag_core.shared_kernel.errors import DomainError  # noqa: E402

KIT = f"rag-core {__version__} (phase 7 issues)"
SEPARATOR_START = "======== PHASE 7 SUMMARY (paste this block) ========"
SEPARATOR_END = "======== END PHASE 7 SUMMARY ========"
CASE = "AR-ISS-024"


def find_root(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.resolve()
    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents, ROOT_CANDIDATE]:
        if (candidate / "pyproject.toml").is_file() and (candidate / "data" / "issues").is_dir():
            return candidate
    raise SystemExit("could not find the repo root (pyproject.toml + data/issues/)")


def invariant_checks(issue) -> dict[str, bool]:  # type: ignore[no-untyped-def]
    """Run the closure rules on a copy; True means the rule held."""
    results: dict[str, bool] = {}
    work = copy.deepcopy(issue)
    try:
        work.transition(IssueStatus.RESOLVED)
        results["parent_cannot_resolve_with_open_subissues"] = False
    except DomainError:
        results["parent_cannot_resolve_with_open_subissues"] = True
    try:
        work.transition_subissue("WIN", IssueStatus.IN_PROGRESS)
        work.transition_subissue("WIN", IssueStatus.RESOLVED)
        results["subissue_waits_for_dependency"] = False
    except DomainError:
        results["subissue_waits_for_dependency"] = True
    try:
        work.transition(IssueStatus.CLOSED)
        results["illegal_transition_rejected"] = False
    except DomainError:
        results["illegal_transition_rejected"] = True
    # Happy path: HW → WIN → WEB → LEG resolved, then the parent resolves and closes.
    happy = copy.deepcopy(issue)
    try:
        for code in ("HW", "WIN", "WEB", "LEG"):
            sub = happy.subissue(code)
            if sub.status is IssueStatus.BLOCKED:
                happy.transition_subissue(code, IssueStatus.IN_PROGRESS)
            happy.transition_subissue(code, IssueStatus.RESOLVED)
        happy.transition(IssueStatus.RESOLVED)
        happy.transition_subissue("WIN", IssueStatus.REOPENED, reason="multi-station test failed")
        reopened = happy.status is IssueStatus.REOPENED
        results["failed_subissue_reopens_resolved_parent"] = reopened
    except DomainError:
        results["failed_subissue_reopens_resolved_parent"] = False
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 7 issue registry check.")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--pytest-passed", default=None)
    parser.add_argument("--pytest-failed", default=None)
    parser.add_argument("--pytest-errors", default=None)
    parser.add_argument("--pytest-skipped", default=None)
    parser.add_argument("--pytest-exit", default=None)
    parser.add_argument("--pytest-line", default=None)
    parser.add_argument("--python-version", default=None)
    parser.add_argument("--prior", default="", help="earlier steps as name=exit,... (e.g. ingest=0,dedup=0)")
    args = parser.parse_args()

    root = find_root(args.root)
    org = HierarchyOrgDirectory.from_registry(root / "data" / "registry")
    loaded = load_issue_registry(root / "data" / "issues", org)
    report = loaded.report
    issues = loaded.issues
    subs = [s for i in issues for s in i.subissues]

    status_counts = Counter(i.status.value for i in issues)
    category_counts = Counter(i.status.category.value for i in issues)
    sub_status = Counter(s.status.value for s in subs)
    positions = {}
    for issue in issues:
        pos = issue.relative_position(org)
        positions[str(issue.identifier)] = {
            "owner": pos.owner, "layer": pos.owner_layer, "depth": pos.owner_depth, "scope": pos.scope.value,
            "common_ancestor": pos.common_ancestor, "escalation": f"{pos.escalation_action}->{pos.escalation_target}",
        }
    scope_counts = Counter(p["scope"] for p in positions.values())

    case = next((i for i in issues if str(i.identifier) == CASE), None)
    decomposition: dict[str, object] = {}
    sub_positions: dict[str, str] = {}
    invariants: dict[str, bool] = {}
    if case is not None:
        fresh = copy.deepcopy(case)
        fresh.subissues = []
        drafts = RuleBasedDecomposer(directory=org).decompose(fresh)
        seeded = {s.code: str(s.owner_node) for s in case.subissues}
        generated = {d.code: d.owner_node for d in drafts}
        decomposition = {
            "generated": [{"code": d.code, "owner": d.owner_node, "depends_on": list(d.depends_on), "matched": list(d.matched)} for d in drafts],
            "matches_seed": generated == seeded,
        }
        for s in case.subissues:
            p = case.subissue_position(s.code, org)
            sub_positions[str(s.identifier)] = f"{p.scope.value}->{p.escalation_target}"
        invariants = invariant_checks(case)

    comparator = IssueComparator()
    comparisons = []
    for sample in loaded.samples:
        result = comparator.compare(issue_from_sample(sample), issues)
        best = result.best
        ok_label = result.label.value == sample.get("expected_label")
        expected_best = sample.get("expected_best")
        ok_best = expected_best is None or (best is not None and best.key == expected_best)
        comparisons.append(
            {
                "id": sample["id"], "language": sample.get("language"), "label": result.label.value,
                "best": best.key if best else None, "score": best.score if best else 0.0,
                "text": best.breakdown.text if best else 0.0, "meta": best.breakdown.meta if best else 0.0,
                "via": best.via if best else None,
                "expected_label": sample.get("expected_label"), "expected_best": expected_best,
                "ok": ok_label and ok_best,
                "top3": [{"key": c.key, "label": c.label.value, "score": c.score} for c in result.candidates[:3]],
            }
        )

    prior = {}
    for part in filter(None, (p.strip() for p in args.prior.split(","))):
        name, _, code = part.partition("=")
        prior[name] = code
    checks = {
        "pytest": args.pytest_exit in (None, "0"),
        "prior_steps": all(v == "0" for v in prior.values()),
        "registry_valid": report.ok,
        "decomposition_matches_seed": bool(decomposition.get("matches_seed")),
        "comparison_expectations": all(c["ok"] for c in comparisons) and bool(comparisons),
        "invariants": bool(invariants) and all(invariants.values()),
    }
    status = "PASS" if all(checks.values()) else "FAIL"

    payload = {
        "kit": KIT, "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "status": status,
        "checks": checks, "prior_steps": prior,
        "validation": {"errors": [str(e) for e in report.errors], "warnings": [str(w) for w in report.warnings]},
        "issues": len(issues), "sub_issues": len(subs), "status_counts": dict(status_counts),
        "status_categories": dict(category_counts), "sub_issue_status": dict(sub_status),
        "positions": positions, "case_sub_issue_positions": sub_positions, "decomposition": decomposition,
        "invariants": invariants, "comparisons": comparisons,
        "thresholds": {"duplicate_score": DUPLICATE_SCORE, "duplicate_min_text": DUPLICATE_MIN_TEXT, "related_score": RELATED_SCORE},
    }
    out_dir = args.out or (root / "results" / "phase-07")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / f"issue-check-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print(SEPARATOR_START)
    print(f"status: {status}")
    print(f"kit: {KIT}")
    if args.python_version:
        print(f"python: {args.python_version}")
    if args.pytest_exit is not None:
        print(f"pytest_exit: {args.pytest_exit}")
        print(f"pytest_passed: {args.pytest_passed or 0}")
        print(f"pytest_failed: {args.pytest_failed or 0}")
        print(f"pytest_errors: {args.pytest_errors or 0}")
        print(f"pytest_skipped: {args.pytest_skipped or 0}")
    if prior:
        print("prior_steps: " + " ".join(f"{k}={v}" for k, v in prior.items()))
    print(f"issue_validation_errors: {len(report.errors)}")
    print(f"issue_validation_warnings: {len(report.warnings)}")
    for e in report.errors[:15]:
        print(f"  - {e}")
    print(f"issues: {len(issues)}")
    print(f"sub_issues: {len(subs)}")
    print("issue_status: " + " ".join(f"{k}={v}" for k, v in sorted(status_counts.items())))
    print("status_categories: " + " ".join(f"{k}={v}" for k, v in sorted(category_counts.items())))
    print("sub_issue_status: " + " ".join(f"{k}={v}" for k, v in sorted(sub_status.items())))
    print("issue_scope: " + " ".join(f"{k}={v}" for k, v in sorted(scope_counts.items())))
    if case is not None:
        cp = positions[CASE]
        print(f"azarpakhsh_position: owner={cp['owner']} L{cp['layer']} depth={cp['depth']} {cp['scope']} escalation={cp['escalation']}")
        print("azarpakhsh_decomposition: " + " ".join(f"{d['code']}->{d['owner']}" for d in decomposition["generated"])  # type: ignore[index,union-attr]
              + f" (matches_seed={decomposition['matches_seed']})")
        print("azarpakhsh_sub_positions: " + " ".join(f"{k.split('/')[1]}={v}" for k, v in sub_positions.items()))
        print("invariants: " + " ".join(f"{k}={'ok' if v else 'FAIL'}" for k, v in invariants.items()))
    print(f"comparison_thresholds: duplicate>={DUPLICATE_SCORE} (text>={DUPLICATE_MIN_TEXT}) related>={RELATED_SCORE}")
    for c in comparisons:
        print(
            f"compare {c['id']} ({c['language']}): {c['label']} best={c['best']} score={c['score']:.3f} "
            f"text={c['text']:.3f} meta={c['meta']:.3f} expected={c['expected_label']} {'ok' if c['ok'] else 'MISMATCH'}"
        )
    print("checks: " + " ".join(f"{k}={'ok' if v else 'FAIL'}" for k, v in checks.items()))
    print(f"results_json: {out_json}")
    print(SEPARATOR_END)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
