#!/usr/bin/env python3
"""Phase 6: load + validate the layer / node registry and the document map.

* Validates ``data/registry/{layer,node}-registry.csv`` and
  ``document-node-map.csv`` against the hierarchy rules (R1–R5 + Phase 6).
* Builds the ``Organization`` aggregate, reports layers, nodes per layer,
  leaves, max depth, document ownership coverage, transfer-requirement
  coverage and retrieval-scope sizes per node.
* Runs the add / move / retire workflows on an in-memory copy (the CSVs are
  never modified) to show knowledge reassignment.
* Prints a ``PHASE 6 SUMMARY`` block and writes ``results/phase-06/hierarchy-<UTC>.json``.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT_CANDIDATE = Path(__file__).resolve().parents[1]
_src = ROOT_CANDIDATE / "src"
if _src.is_dir() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from rag_core.hierarchy.application.workflows import (  # noqa: E402
    HierarchyWorkflowService,
    catalog_index,
    coverage,
    load_and_validate,
    scope_sizes,
)
from rag_core.hierarchy.domain.model import Node, NodeType  # noqa: E402
from rag_core.hierarchy.domain.scope import route_question  # noqa: E402
from rag_core.shared_kernel.identifiers import NodeIdentifier  # noqa: E402
from rag_core.shared_kernel.layer import LayerIndex  # noqa: E402

KIT = "rag-core 0.6.0 (phase 6)"
SEPARATOR_START = "======== PHASE 6 SUMMARY (paste this block) ========"
SEPARATOR_END = "======== END PHASE 6 SUMMARY ========"
N = NodeIdentifier


def find_root(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.resolve()
    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents, ROOT_CANDIDATE]:
        if (candidate / "pyproject.toml").is_file() and (candidate / "data" / "registry").is_dir():
            return candidate
    raise SystemExit("could not find the repo root (pyproject.toml + data/registry/)")


def simulate_workflows(registry_dir: Path) -> dict[str, object]:
    """Run workflows on a fresh in-memory copy; returns what happened."""
    loaded = load_and_validate(registry_dir)
    svc = HierarchyWorkflowService(loaded.organization, loaded.ownership)
    org = svc.organization
    svc.add_node(
        Node(N("N-SW-DATA"), "Data Team (simulated)", "تیم داده (شبیه‌سازی)", NodeType.TEAM, LayerIndex(3), N("N-SW"), is_leaf=True)
    )
    svc.move_node(N("N-SW-DATA"), N("N-HW"))
    changes = svc.retire_node(N("N-SW-VIS"), N("N-SW-UX"), reason="simulated merge into UX")
    events = [e.name for e in org.events if e.name in {"NodeRegistered", "NodeMoved", "NodeRetired"}]
    return {
        "added": "N-SW-DATA under N-SW",
        "moved": "N-SW-DATA -> N-HW",
        "path_after_move": org.path_string(N("N-SW-DATA")),
        "retired": "N-SW-VIS -> successor N-SW-UX",
        "reassigned": [f"{c.document_id.value}:{c.role.value}" for c in changes],
        "events": dict(Counter(events[-3:])),
        "routing_examples": {
            "N-SW-WEB asks, evidence N-SW-MOB": str(route_question(org, N("N-SW-WEB"), [N("N-SW-MOB")]).target),
            "N-SW-WEB asks, evidence N-HW-REP": str(route_question(org, N("N-SW-WEB"), [N("N-HW-REP")]).target),
            "N-SW-WEB asks, reserved decision": str(
                route_question(org, N("N-SW-WEB"), [N("N-SW-WEB")], reserved_decision=True).target
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 6 hierarchy registry check.")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--pytest-passed", default=None)
    parser.add_argument("--pytest-failed", default=None)
    parser.add_argument("--pytest-errors", default=None)
    parser.add_argument("--pytest-exit", default=None)
    parser.add_argument("--pytest-line", default=None)
    parser.add_argument("--python-version", default=None)
    args = parser.parse_args()

    root = find_root(args.root)
    registry_dir = root / "data" / "registry"
    catalog = catalog_index()
    loaded = load_and_validate(registry_dir, catalog)
    report = loaded.report
    payload: dict[str, object] = {
        "kit": KIT,
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "registry_dir": str(registry_dir),
        "validation": {
            "errors": [str(i) for i in report.errors],
            "warnings": [str(i) for i in report.warnings],
        },
    }
    org, ownership = loaded.organization, loaded.ownership
    summary: dict[str, object] = {}
    if org is not None and ownership is not None:
        layers = sorted(org.layers.values(), key=lambda l: l.index.value)
        per_layer = {l.code: len(org.nodes_on_layer(l.index.value)) for l in layers}
        transfer_complete = [l.code for l in layers if l.transfer is not None and l.transfer.is_complete]
        cov = coverage(org, ownership, sorted(catalog))
        sizes = scope_sizes(org, ownership, catalog)
        summary = {
            "layers": len(layers),
            "nodes": len(org.active_nodes()),
            "nodes_per_layer": per_layer,
            "leaves": sorted(str(n.identifier) for n in org.leaves()),
            "max_depth": org.max_depth(),
            "transfer_complete": transfer_complete,
            "coverage": cov.as_dict(),
            "scope_sizes": sizes,
            "q3_exemption": f"N-LIB {org.get(N('N-LIB')).layer} -> {org.get(N('N-LIB')).parent_id}",
        }
        payload["summary"] = summary
        payload["layers"] = [
            {
                "code": l.code,
                "name_en": l.name_en,
                "detail_level_received": l.default_detail_level,
                "transfer": None
                if l.transfer is None
                else {
                    "direction": l.transfer.direction.value,
                    "target": l.transfer.target.code,
                    "min_artefacts": list(l.transfer.min_artefacts),
                    "approvals": list(l.transfer.approvals),
                    "gaps": l.transfer.gaps(),
                },
            }
            for l in layers
        ]
        payload["paths"] = {str(n.identifier): org.path_string(n.identifier) for n in org.active_nodes()}
        payload["workflow_simulation"] = simulate_workflows(registry_dir)

    unmapped = summary.get("coverage", {}).get("documents_unmapped", ["?"]) if summary else ["?"]  # type: ignore[union-attr]
    ok = (
        report.ok
        and org is not None
        and not unmapped
        and len(summary.get("transfer_complete", [])) == summary.get("layers")  # type: ignore[arg-type]
        and (args.pytest_exit in (None, "0"))
    )
    status = "PASS" if ok else "FAIL"
    payload["status"] = status

    out_dir = args.out or (root / "results" / "phase-06")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_json = out_dir / f"hierarchy-{stamp}.json"
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
    print(f"validation_errors: {len(report.errors)}")
    print(f"validation_warnings: {len(report.warnings)}")
    for issue in report.errors[:20]:
        print(f"  - {issue}")
    if summary:
        cov = summary["coverage"]
        print(f"layers: {summary['layers']}")
        print("nodes_per_layer: " + " ".join(f"{k}={v}" for k, v in summary["nodes_per_layer"].items()))  # type: ignore[union-attr]
        print(f"nodes_total: {summary['nodes']}")
        print(f"leaves: {len(summary['leaves'])}")  # type: ignore[arg-type]
        print(f"max_depth: {summary['max_depth']}")
        print(f"q3_exemption: {summary['q3_exemption']}")
        print(f"docs_mapped: {cov['documents_mapped']}/{cov['documents_total']}")  # type: ignore[index]
        print(f"docs_unmapped: {len(cov['documents_unmapped'])}")  # type: ignore[index,arg-type]
        print("doc_links: " + " ".join(f"{k}={v}" for k, v in cov["links_by_role"].items()))  # type: ignore[index,union-attr]
        print(f"nodes_owning_docs: {len(cov['nodes_with_owned_docs'])}")  # type: ignore[index,arg-type]
        print(f"leaves_without_owned_docs: {', '.join(cov['leaves_without_owned_docs']) or 'none'}")  # type: ignore[index,arg-type]
        print(f"transfer_requirement_coverage: {len(summary['transfer_complete'])}/{summary['layers']}")  # type: ignore[arg-type]
        sizes = summary["scope_sizes"]
        sample = ["N-BRD", "N-CEO", "N-SW", "N-SW-WEB", "N-ADM-HR", "N-LIB"]
        print("scope_docs: " + " ".join(f"{n}={sizes[n]['visible_documents']}" for n in sample if n in sizes))  # type: ignore[index,operator]
        sim = payload["workflow_simulation"]
        print(f"workflow_sim: add+move -> {sim['path_after_move']}; retire N-SW-VIS -> N-SW-UX reassigned {len(sim['reassigned'])}")  # type: ignore[index,arg-type]
        routing = sim["routing_examples"]  # type: ignore[index]
        print("escalation: " + "; ".join(f"{k} => {v}" for k, v in routing.items()))  # type: ignore[union-attr]
    print(f"results_json: {out_json}")
    print(SEPARATOR_END)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
