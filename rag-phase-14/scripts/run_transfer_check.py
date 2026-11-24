#!/usr/bin/env python3
"""Phase 11: cyclic node processing and upward knowledge transfer.

Always (no Ollama needed):
* Loads the layer / node registry (Phase 6), the active document versions
  (Phase 4/5 corpus build), the issues (Phase 7), the executors and the
  offline IKE graph of AR-ISS-024 (Phase 9: leads and knowledge lacks).
* Builds the bottom-up processing plan (leaves first, CEO last; the Board only
  receives, the L4 library does not summarize upward) and checks the detail
  levels against the layer registry.
* Runs cycle ``1403-Q2`` (config/transfer.yaml): every node builds one
  TransferPackage for its parent at the receiving layer's detail level, the
  package is fact-checked and judged by the Phase 10 rule judge (18/20), and
  only accepted packages go up.
* Stores the latest package per (cycle, node) in SQLite with history and
  exports CSVs (exports/transfer-packages/<cycle>/); reads them back.
* Re-runs the cycle on a scratch database: the second run must store nothing
  new; a simulated status change must add revision 2 only for the changed
  path and keep revision 1 as history.
* Negative controls: broken copies of the package texts must be rejected.

Live (only if local Ollama answers and qwen3:8b is installed):
* AI transfer suggestions (qwen3:8b, think off, JSON) for the most important
  packages, fact-checked; templates and suggestions judged by qwen3:8b and the
  rule judge together (combined judge). Without Ollama: live SKIPPED.

The status depends on pytest, the earlier steps and the offline checks only.
Prints the ``PHASE 11 SUMMARY`` block and writes
``results/phase-11/transfer-check-<UTC>.json``.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import time
import traceback

ROOT_CANDIDATE = Path(__file__).resolve().parents[1]
_src = ROOT_CANDIDATE / "src"
if _src.is_dir() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from rag_core import __version__  # noqa: E402
from rag_core.executors.application.services import (
    ExecutorMatchingService,
    load_executor_registry,
)  # noqa: E402
from rag_core.executors.infrastructure.hierarchy_acl import HierarchyTeamDirectory  # noqa: E402
from rag_core.executors.infrastructure.issues_acl import referral_requests  # noqa: E402
from rag_core.hierarchy.application.workflows import load_and_validate  # noqa: E402
from rag_core.ike.application.services import IkeService  # noqa: E402
from rag_core.ike.domain.summary import digest  # noqa: E402
from rag_core.ike.infrastructure.executors_acl import executor_names, referrals_by_item  # noqa: E402
from rag_core.ike.infrastructure.issues_acl import issue_view  # noqa: E402
from rag_core.ike.infrastructure.retrieval_acl import RetrieverKnowledgeSearch  # noqa: E402
from rag_core.issues.application.services import load_issue_registry  # noqa: E402
from rag_core.issues.infrastructure.hierarchy_acl import HierarchyOrgDirectory  # noqa: E402
from rag_core.judging.application.services import LlmJudge, judge_all  # noqa: E402
from rag_core.judging.domain.metrics import acceptance  # noqa: E402
from rag_core.judging.domain.rule_judge import RuleBasedJudge  # noqa: E402
from rag_core.judging.infrastructure.config import JudgeSettings, load_judge_settings  # noqa: E402
from rag_core.judging.infrastructure.prompt_yaml import load_judge_prompts, load_rubric  # noqa: E402
from rag_core.processing.application.services import CycleProcessor, CycleRun  # noqa: E402
from rag_core.processing.domain.cycle import ProcessingCycle  # noqa: E402
from rag_core.processing.domain.plan import (
    REPOSITORY_REASON,
    ROOT_REASON,
    ProcessingPlan,
    build_plan,
)  # noqa: E402
from rag_core.processing.infrastructure.hierarchy_acl import tree_nodes  # noqa: E402
from rag_core.qa.domain.fact_check import CitedFactValidator  # noqa: E402
from rag_core.rag.application.corpus import build_corpus_records  # noqa: E402
from rag_core.rag.application.indexing import build_retriever  # noqa: E402
from rag_core.rag.infrastructure.config import RagSettings, load_settings  # noqa: E402
from rag_core.rag.infrastructure.ollama import (
    OllamaChatModel,
    OllamaClient,
    OllamaError,
)  # noqa: E402
from rag_core.transfer.application.services import SuggestionService, TransferService  # noqa: E402
from rag_core.transfer.domain.builder import TransferPackageBuilder  # noqa: E402
from rag_core.transfer.domain.levels import RuleBook  # noqa: E402
from rag_core.transfer.domain.review import BuiltPackage, PackageReviewer  # noqa: E402
from rag_core.transfer.infrastructure.config import (
    TransferSettings,
    load_transfer_settings,
)  # noqa: E402
from rag_core.transfer.infrastructure.csv_export import (
    export_latest,
    round_trip_problems,
)  # noqa: E402
from rag_core.transfer.infrastructure.ike_acl import leads_and_lacks  # noqa: E402
from rag_core.transfer.infrastructure.judging_acl import (  # noqa: E402
    CaseJudgeAdapter,
    CombinedPackageJudge,
    package_case,
)
from rag_core.transfer.infrastructure.sources_acl import (  # noqa: E402
    build_knowledge,
    document_versions,
    layer_rules_from_registry,
    sender_level_mismatches,
    with_item_status,
)
from rag_core.transfer.infrastructure.sqlite_store import SqliteTransferStore  # noqa: E402

KIT = f"rag-core {__version__} (phase 11 cyclic processing + transfer)"
SEPARATOR_START = "======== PHASE 11 SUMMARY ========"
SEPARATOR_END = "======== END PHASE 11 SUMMARY ========"
TOP_K = 8
LANGS = ("fa", "en")
SKIP_LABELS = {ROOT_REASON: "root", REPOSITORY_REASON: "repository"}
NEG_NUMBER = {"en": " Penalty 777 million toman.", "fa": " جریمهٔ ۷۷۷ میلیون تومان."}
NEG_ID = {"en": " See AR-ISS-099.", "fa": " به AR-ISS-099 نگاه کنید."}


def find_root(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.resolve()
    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents, ROOT_CANDIDATE]:
        if (candidate / "pyproject.toml").is_file() and (
            candidate / "config" / "transfer.yaml"
        ).is_file():
            return candidate
    raise SystemExit(
        "could not find the repo root (pyproject.toml + config/transfer.yaml)"
    )


def parse_prior(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in filter(None, (p.strip() for p in text.split(","))):
        name, _, code = part.partition("=")
        out[name.strip()] = code.strip() or "?"
    return out


def rel(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def ike_leads(root: Path, settings: RagSettings, corpus, org, case_id: str):  # noqa: ANN001, ANN201
    """Phase 9 offline IKE graph of the case → leads, knowledge lacks and executor list."""
    teams = HierarchyTeamDirectory(org)
    loaded = load_executor_registry(root / "data" / "executors", teams)
    executors = loaded.executors
    issues = load_issue_registry(
        root / "data" / "issues", HierarchyOrgDirectory(org)
    ).issues
    case = next((i for i in issues if str(i.identifier) == case_id), None)
    if case is None or not executors:
        raise RuntimeError(f"{case_id} or the executor registry is missing")
    plans = ExecutorMatchingService(loaded.repository()).plans(referral_requests(case))
    view = issue_view(case)
    lexical = build_retriever(
        corpus.records, scope=corpus.scope, config=settings.retrieval
    )
    ike = IkeService(
        RetrieverKnowledgeSearch(lexical, corpus.scope),
        top_k=TOP_K,
        min_lexical=settings.qa.evidence_min_lexical,
        min_vector=settings.qa.evidence_min_vector,
    )
    graph = ike.build(view, referrals_by_item(plans, executors), ike.compare(view))
    leads, lacks = leads_and_lacks(digest(view, graph), executor_names(executors))
    return leads, lacks, executors, issues


def probe_ollama(
    settings: RagSettings, model: str
) -> tuple[OllamaClient | None, str, dict]:
    info: dict[str, object] = {"base_url": settings.ollama.base_url}
    try:
        client = OllamaClient(
            settings.ollama.base_url,
            timeout_s=settings.ollama.generate_timeout_s,
            retries=settings.ollama.retries,
        )
        info["version"] = client.version(timeout=settings.ollama.connect_timeout_s)
        names = client.model_names(timeout=max(5.0, settings.ollama.connect_timeout_s))
    except OllamaError as exc:
        return None, f"Ollama not reachable at {settings.ollama.base_url} ({exc})", info
    info["models"] = names
    if not OllamaClient.has_model(names, model):
        return None, f"model not installed: {model} (run: ollama pull {model})", info
    return client, "", info


def mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 3) if values else None


def negative_cases(packages: list[BuiltPackage]) -> list:  # noqa: ANN201
    """Broken copies of every package text: invented number, invented id, all item lines removed."""
    cases = []
    for p in packages:
        draft = p.draft
        for lang in LANGS:
            base = package_case(draft, lang)
            text = draft.text(lang)
            cases.append(base.mutated("wrong_number", text + NEG_NUMBER[lang]))
            cases.append(base.mutated("fabricated_id", text + NEG_ID[lang]))
            items = draft.rendered.expected_items
            if items:
                kept = [
                    line
                    for line in text.splitlines()
                    if not any(i in line for i in items)
                ]
                cases.append(base.mutated("drop_items", "\n".join(kept)))
    return cases


def package_line(p: BuiltPackage) -> str:
    d = p.draft
    groups = len({i.parent_id for i in d.items})
    review = p.review
    totals = (
        ",".join(f"{lang}:{review.total('rule', lang)}" for lang in LANGS)
        if review
        else "-"
    )
    return (
        f"  {d.source_node}->{d.target_node}: {d.detail_level} items={len(d.items)} issues={groups} "
        f"omitted={len(d.omitted)} words=fa:{d.words('fa')},en:{d.words('en')} rule={totals} {p.status}"
        + (f" reasons={';'.join(review.reasons)}" if review and review.reasons else "")
    )


def main() -> int:  # noqa: C901 - one linear report
    parser = argparse.ArgumentParser(
        description="Phase 11 cyclic node processing and upward transfer."
    )
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument(
        "--config", type=Path, default=None, help="config/rag.yaml (Ollama endpoint)"
    )
    parser.add_argument(
        "--judge-config", type=Path, default=None, help="config/judge.yaml"
    )
    parser.add_argument(
        "--transfer-config", type=Path, default=None, help="config/transfer.yaml"
    )
    parser.add_argument(
        "--out", type=Path, default=None, help="folder for transfer-check-*.json"
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="SQLite file (default from config/transfer.yaml)",
    )
    parser.add_argument(
        "--exports",
        type=Path,
        default=None,
        help="CSV folder (default from config/transfer.yaml)",
    )
    parser.add_argument("--no-live", action="store_true", help="skip the Ollama step")
    for name in ("passed", "failed", "errors", "skipped", "exit", "line"):
        parser.add_argument(f"--pytest-{name}", default=None)
    parser.add_argument("--python-version", default=None)
    parser.add_argument("--prior", default="", help="earlier steps as name=exit,...")
    args = parser.parse_args()

    root = find_root(args.root)
    settings = load_settings(args.config or root / "config" / "rag.yaml")
    jset: JudgeSettings = load_judge_settings(
        args.judge_config or root / "config" / "judge.yaml"
    )
    tset: TransferSettings = load_transfer_settings(
        args.transfer_config or root / "config" / "transfer.yaml"
    )
    out_dir = args.out or root / "results" / "phase-11"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_json = out_dir / f"transfer-check-{stamp}.json"
    db_path = args.db or root / tset.storage.db
    csv_dir = args.exports or root / tset.storage.csv_dir
    t0 = time.perf_counter()
    cycle = ProcessingCycle(tset.cycle.id, tset.cycle.period_end, tset.cycle.trigger)
    errors: list[str] = []

    # ---- registry, corpus versions, issues, executors, IKE
    loaded = load_and_validate(root / "data" / "registry")
    org, ownership = loaded.organization, loaded.ownership
    corpus = build_corpus_records(root)
    versions = document_versions(corpus.records)
    leads: dict = {}
    lacks: dict = {}
    executors: list = []
    issues: list = []
    if org is None or ownership is None:
        errors.append(f"registry invalid: {len(loaded.report.errors)} error(s)")
    else:
        try:
            leads, lacks, executors, issues = ike_leads(
                root, settings, corpus, org, tset.case
            )
        except Exception as exc:  # noqa: BLE001 - reported as a failed check
            errors.append(f"ike: {type(exc).__name__}: {exc}")

    rules = RuleBook()
    rubric = load_rubric(root / jset.files.rubric)
    validator = CitedFactValidator()
    rule_judge = RuleBasedJudge(rubric, validator, jset.rules)
    rule_adapter = CaseJudgeAdapter(rule_judge)
    builder = TransferPackageBuilder(versions)
    reviewer = PackageReviewer(validator, rule_adapter)

    plan = ProcessingPlan(())
    knowledge: dict = {}
    mismatches: list[str] = []
    run: CycleRun | None = None
    store_info: dict[str, object] = {}
    csv_info: dict[str, object] = {}
    rerun: dict[str, object] = {}
    update: dict[str, object] = {}
    if org is not None and ownership is not None:
        knowledge = build_knowledge(
            org, ownership, issues, executors, versions, leads, lacks
        )
        try:
            plan = build_plan(tree_nodes(org))
        except Exception as exc:  # noqa: BLE001 - reported as a failed check
            errors.append(f"plan: {type(exc).__name__}: {exc}")
        mismatches = rules.registry_mismatches(layer_rules_from_registry(org))
        mismatches += sender_level_mismatches(
            org, plan.senders, {r.receiving_layer: r.level.value for r in rules.rules}
        )
        service = TransferService(knowledge, rules, builder, reviewer)
        processor = CycleProcessor(service)

        # ---- the real cycle: SQLite + CSV export
        try:
            with SqliteTransferStore(db_path) as store:
                run = processor.run(cycle, plan, store=store)
                rows = store.latest_all(cycle.cycle_id)
                files = export_latest(rows, csv_dir, cycle.cycle_id)
                problems = round_trip_problems(rows, csv_dir, cycle.cycle_id)
                store_info = {
                    "db": rel(root, db_path),
                    **run.report.counts(),
                    **store.stats(cycle.cycle_id),
                    "all_cycles": store.cycles(),
                }
                csv_info = {
                    "dir": rel(root, csv_dir / cycle.cycle_id),
                    "files": len(files),
                    "problems": problems,
                }
        except Exception as exc:  # noqa: BLE001 - reported as a failed check
            errors.append(f"store: {type(exc).__name__}: {exc}")
            store_info.setdefault("error", f"{type(exc).__name__}: {exc}")

        # ---- idempotent re-run and a simulated update on a scratch database
        try:
            with (
                tempfile.TemporaryDirectory() as tmp,
                SqliteTransferStore(Path(tmp) / "check.sqlite") as scratch,
            ):
                first = processor.run(cycle, plan, store=scratch).report.counts()
                second = processor.run(cycle, plan, store=scratch).report.counts()
                rerun = {
                    "first": first,
                    "second": second,
                    "idempotent": second["unchanged"] == second["built"]
                    and second["inserted"] == 0
                    and second["updated"] == 0,
                }
                u = tset.update_check
                changed = with_item_status(knowledge, u.node, u.item, u.status)
                third_run = CycleProcessor(
                    TransferService(changed, rules, builder, reviewer)
                ).run(cycle, plan, store=scratch)
                third = third_run.report.counts()
                changed_nodes = sorted(
                    s.source_node
                    for s in third_run.report.steps
                    if s.store_action == "updated"
                )
                histories = {
                    n: scratch.history(cycle.cycle_id, n) for n in changed_nodes
                }
                update = {
                    "node": u.node,
                    "item": u.item,
                    "status": u.status,
                    "counts": third,
                    "changed_nodes": changed_nodes,
                    "stats": scratch.stats(cycle.cycle_id),
                    "history_ok": all(
                        len(h) == 2 and [r["is_latest"] for r in h] == [0, 1]
                        for h in histories.values()
                    ),
                }
        except Exception as exc:  # noqa: BLE001 - reported as a failed check
            errors.append(f"rerun: {type(exc).__name__}: {exc}")

    packages: list[BuiltPackage] = list(run.packages.values()) if run else []
    accepted = [p for p in packages if p.accepted]

    # ---- metrics over the packages of the real cycle
    grounded = {
        lang: sum(1 for p in packages if p.review and p.review.grounding[lang].grounded)
        for lang in LANGS
    }
    rule_results = [r for r in rule_adapter.results if r.origin == "transfer-template"]
    rule_stats = acceptance(rule_results[: 2 * len(packages)])
    by_level: dict[str, int] = {}
    items_by_layer: dict[int, int] = {}
    for p in packages:
        by_level[p.detail_level] = by_level.get(p.detail_level, 0) + 1
        items_by_layer[p.target_layer] = items_by_layer.get(p.target_layer, 0) + len(
            p.items
        )
    l0 = [p for p in packages if p.target_layer == 0]
    l0_ok = bool(l0) and all(
        all(
            str(p.draft.package.fields.get(k, "")).strip()
            for k in ("risks", "decisions_requested", "source_references")
        )
        and len(p.draft.package.citations) > 0
        for p in l0
    )
    words_ok = bool(packages) and all(
        p.draft.words(lang) <= p.draft.rule.max_words
        for p in packages
        for lang in LANGS
    )

    # ---- negative controls (rule judge)
    neg = judge_all(rule_judge, negative_cases(accepted))
    neg_kinds: dict[str, dict[str, int]] = {}
    for r in neg:
        kind = r.origin.split(":", 1)[1]
        bucket = neg_kinds.setdefault(kind, {"rejected": 0, "n": 0})
        bucket["n"] += 1
        bucket["rejected"] += int(not r.accepted)
    neg_rejected = sum(1 for r in neg if not r.accepted)

    # ---- live step
    live: dict[str, object] = {"status": "skipped", "reason": "disabled with --no-live"}
    ollama_info: dict[str, object] = {"base_url": settings.ollama.base_url}
    if not args.no_live:
        if not accepted:
            live = {"status": "skipped", "reason": "no accepted package to work on"}
        else:
            client, reason, ollama_info = probe_ollama(settings, tset.model.model)
            if client is None:
                live = {"status": "skipped", "reason": reason}
            else:
                print(
                    "live step: Ollama",
                    ollama_info.get("version"),
                    "→ qwen3:8b transfer suggestions and judge",
                    flush=True,
                )
                try:
                    live = {
                        "status": "ok",
                        **live_step(
                            tset,
                            jset,
                            client,
                            rubric,
                            root,
                            rule_judge,
                            validator,
                            accepted,
                            db_path,
                            cycle.cycle_id,
                        ),
                    }
                except Exception as exc:  # noqa: BLE001 - the live step never breaks the kit status
                    live = {
                        "status": "fail",
                        "reason": f"{type(exc).__name__}: {exc}",
                        "traceback": traceback.format_exc(limit=5),
                    }
    total_s = time.perf_counter() - t0

    # ---- checks
    prior = parse_prior(args.prior)
    counts = run.report.counts() if run else {}
    checks = {
        "pytest": args.pytest_exit in (None, "0", 0),
        "prior_steps": all(v == "0" for v in prior.values()),
        "registry_loaded": org is not None
        and bool(executors)
        and bool(issues)
        and not any(e.startswith(("registry", "ike")) for e in errors),
        "records_built": bool(corpus.records) and not corpus.failures,
        "plan_bottom_up": bool(plan.steps) and plan.is_bottom_up(),
        "detail_levels_match_registry": org is not None and not mismatches,
        "packages_built": bool(plan.steps)
        and counts.get("built") == len(plan.steps)
        and counts.get("failed") == 0,
        "packages_grounded": bool(packages)
        and all(grounded[lang] == len(packages) for lang in LANGS),
        "packages_accepted": bool(packages) and len(accepted) == len(packages),
        "l0_required_fields": l0_ok,
        "word_limits": words_ok,
        "negative_controls_rejected": bool(neg) and neg_rejected == len(neg),
        "store_idempotent": bool(rerun.get("idempotent")),
        "update_revision_history": bool(update.get("changed_nodes"))
        and bool(update.get("history_ok")),
        "csv_round_trip": bool(csv_info.get("files")) and not csv_info.get("problems"),
    }
    status = "PASS" if all(checks.values()) else "FAIL"

    payload = {
        "kit": KIT,
        "run_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": status,
        "checks": checks,
        "errors": errors,
        "python": args.python_version,
        "pytest": {
            "passed": args.pytest_passed,
            "failed": args.pytest_failed,
            "errors": args.pytest_errors,
            "skipped": args.pytest_skipped,
            "exit": args.pytest_exit,
            "result_line": args.pytest_line,
        },
        "prior_steps": prior,
        "cycle": {
            "id": cycle.cycle_id,
            "period_start": tset.cycle.period_start,
            "period_end": cycle.period_end,
            "trigger": cycle.trigger,
        },
        "plan": {
            "steps": [s.__dict__ for s in plan.steps],
            "skipped": [s.__dict__ for s in plan.skipped],
            "bottom_up": plan.is_bottom_up() if plan.steps else False,
        },
        "rules": [
            {
                "level": r.level.value,
                "receiving_layer": r.receiving_layer,
                "max_items": r.max_items,
                "max_words": r.max_words,
                "aggregation": r.aggregation.value,
                "include_closed": r.include_closed,
                "show_people": r.show_people,
                "show_gaps": r.show_gaps,
                "show_capacity": r.show_capacity,
                "citation_level": r.citation_level,
                "required_fields": list(r.required_fields),
            }
            for r in rules.rules
        ],
        "registry_mismatches": mismatches,
        "knowledge": {
            "nodes": len(knowledge),
            "documents": sum(len(k.documents) for k in knowledge.values()),
            "items": sum(len(k.items) for k in knowledge.values()),
            "nodes_with_items": sum(1 for k in knowledge.values() if k.items),
            "executors": sum(len(k.executors) for k in knowledge.values()),
            "ike_leads": sum(1 for v in leads.values() if v[0]),
            "ike_lacks": sum(len(v) for v in lacks.values()),
        },
        "report": run.report.to_dict() if run else None,
        "packages": [p.content() for p in packages],
        "grounded": grounded,
        "rule_judge": rule_stats,
        "negative_controls": {
            "n": len(neg),
            "rejected": neg_rejected,
            "by_kind": neg_kinds,
            "accepted_cases": [r.case_id for r in neg if r.accepted],
        },
        "store": store_info,
        "csv": csv_info,
        "rerun": rerun,
        "update": update,
        "ollama": ollama_info,
        "live": live,
        "timings": {"total_s": round(total_s, 2), "corpus_s": round(corpus.seconds, 2)},
    }
    out_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    # ---- summary block
    print()
    print(SEPARATOR_START)
    print(f"status: {status}")
    print(f"kit: {KIT}")
    print(f"python: {args.python_version}")
    print(f"pytest_exit: {args.pytest_exit}")
    print(f"pytest_passed: {args.pytest_passed}")
    print(f"pytest_failed: {args.pytest_failed}")
    print(f"pytest_errors: {args.pytest_errors}")
    print(f"pytest_skipped: {args.pytest_skipped}")
    print("prior_steps: " + (" ".join(f"{k}={v}" for k, v in prior.items()) or "none"))
    if errors:
        print("errors: " + " | ".join(errors))
    print(
        f"cycle: {cycle.cycle_id} period={tset.cycle.period_start}..{cycle.period_end} trigger={cycle.trigger}"
    )
    to_layer: dict[int, int] = {}
    for s in plan.steps:
        to_layer[s.target_layer] = to_layer.get(s.target_layer, 0) + 1
    skipped = (
        ",".join(
            f"{s.node_id}:{SKIP_LABELS.get(s.reason, s.reason)}" for s in plan.skipped
        )
        or "-"
    )
    print(
        f"plan: senders={len(plan.steps)} skipped={len(plan.skipped)} bottom_up={plan.is_bottom_up() if plan.steps else False} "
        + " ".join(f"to_L{k}={v}" for k, v in sorted(to_layer.items(), reverse=True))
        + f" skipped_nodes={skipped}"
    )
    print(
        "detail_levels: "
        + " ".join(
            f"L{r.receiving_layer}={r.level.value}({'groups' if r.aggregation.value == 'by_issue' else 'items'}<="
            f"{r.max_items},words<={r.max_words})"
            for r in reversed(rules.rules)
            if r.receiving_layer < 3
        )
        + f" registry_mismatches={len(mismatches)}"
    )
    k = payload["knowledge"]
    print(
        f"knowledge: nodes={k['nodes']} documents_active={k['documents']} nodes_with_items={k['nodes_with_items']} "
        f"items={k['items']} executors={k['executors']} ike_leads={k['ike_leads']} ike_lacks={k['ike_lacks']}"
    )
    print(
        f"packages: built={counts.get('built', 0)}/{len(plan.steps)} accepted={counts.get('accepted', 0)} "
        f"rejected={counts.get('rejected', 0)} failed={counts.get('failed', 0)} levels="
        + ",".join(f"{lvl}:{n}" for lvl, n in by_level.items())
    )
    omitted_l0 = sum(len(p.omitted) for p in l0)
    dropped = sum(len(p.draft.dropped_closed) for p in packages)
    print(
        "package_items: "
        + " ".join(
            f"to_L{lay}={n}" for lay, n in sorted(items_by_layer.items(), reverse=True)
        )
        + f" omitted_at_L0={omitted_l0} dropped_closed={dropped}"
    )
    for p in sorted(packages, key=lambda x: (x.target_layer, x.source_node)):
        if p.items or p.target_layer < 2 or not p.accepted:
            print(package_line(p))
    if run:
        for s in run.report.steps:
            if s.outcome.value == "failed":
                print(f"  FAILED {s.source_node}->{s.target_node}: {s.reason}")
    print(
        f"fact_check: grounded fa={grounded['fa']}/{len(packages)} en={grounded['en']}/{len(packages)}"
    )
    print(
        f"rule_judge: accepted={rule_stats['accepted']}/{rule_stats['n']} mean_total={rule_stats['mean_total']} "
        f"min_total={rule_stats['min_total']} (accept >= {rubric.accept_total}/{rubric.out_of})"
    )
    print(
        f"negative_controls: rejected={neg_rejected}/{len(neg)} by_kind="
        + ",".join(f"{kind}:{v['rejected']}/{v['n']}" for kind, v in neg_kinds.items())
    )
    if store_info and "error" not in store_info:
        print(
            f"store: db={store_info['db']} inserted={store_info['inserted']} unchanged={store_info['unchanged']} "
            f"updated={store_info['updated']} rows={store_info['rows']} latest={store_info['latest']} "
            f"max_revision={store_info['max_revision']} cycles={store_info['cycles']}"
        )
    else:
        print(f"store: FAIL {store_info.get('error', 'not run')}")
    print(
        f"csv: files={csv_info.get('files', 0)} dir={csv_info.get('dir', '-')} "
        f"round_trip_problems={len(csv_info.get('problems', []) or [])}"
    )  # type: ignore[arg-type]
    if rerun:
        f1, f2 = rerun["first"], rerun["second"]  # type: ignore[index]
        print(
            f"rerun: first=inserted:{f1['inserted']} second=unchanged:{f2['unchanged']} "  # type: ignore[index]
            f"inserted:{f2['inserted']} updated:{f2['updated']} idempotent={rerun['idempotent']}"
        )  # type: ignore[index]
    if update:
        c3 = update["counts"]
        st = update["stats"]
        print(
            f"update: {update['item']}@{update['node']}->{update['status']} changed={c3['updated']} "  # type: ignore[index]
            f"({','.join(update['changed_nodes'])}) unchanged={c3['unchanged']} rows={st['rows']} "  # type: ignore[index,arg-type]
            f"latest={st['latest']} max_revision={st['max_revision']} history_ok={update['history_ok']}"
        )  # type: ignore[index]
    print(
        f"live: {live['status']}"
        + (f" ({live.get('reason')})" if live.get("reason") else "")
    )
    if live["status"] == "ok":
        print_live(live)
    print(
        "checks: "
        + " ".join(f"{k2}={'ok' if v else 'FAIL'}" for k2, v in checks.items())
    )
    print(f"results_json: {out_json}")
    print(SEPARATOR_END)
    return 0 if status == "PASS" else 1


def live_targets(packages: list[BuiltPackage], limit: int) -> list[BuiltPackage]:
    """Most important first: the Board brief, the deputies' packages, then teams with the most items."""
    ranked = sorted(
        packages, key=lambda p: (p.target_layer, -len(p.items), p.source_node)
    )
    return [p for p in ranked if p.items][:limit]


def live_step(
    tset: TransferSettings,
    jset: JudgeSettings,
    client: OllamaClient,
    rubric,
    root: Path,  # noqa: ANN001
    rule_judge: RuleBasedJudge,
    validator: CitedFactValidator,
    packages: list[BuiltPackage],
    db_path: Path,
    cycle_id: str,
) -> dict:
    m = tset.model
    chat = OllamaChatModel(
        client,
        m.model,
        dict(m.options),
        m.think,
        m.keep_alive,
        m.timeout_s,
        response_format=m.format or None,
    )
    rule_adapter = CaseJudgeAdapter(rule_judge)
    llm_adapter = None
    if tset.live.llm_judge:
        jm = jset.model
        judge_chat = OllamaChatModel(
            client,
            jm.model,
            dict(jm.options),
            jm.think,
            jm.keep_alive,
            jm.timeout_s,
            response_format=jm.format or None,
        )
        prompts = load_judge_prompts(root / jset.files.prompt_dir)
        llm = LlmJudge(
            rubric,
            prompts,
            judge_chat,
            name=f"llm:{jm.model}",
            retries=jset.run.retries,
            sources_char_budget=jset.run.sources_char_budget,
        )
        llm_adapter = CaseJudgeAdapter(llm)
    judge = (
        CombinedPackageJudge(rule_adapter, llm_adapter)
        if llm_adapter
        else CombinedPackageJudge(rule_adapter)
    )
    service = SuggestionService(chat, validator, judge)
    targets = live_targets(packages, tset.live.max_packages)
    t0 = time.perf_counter()
    suggestions = []
    templates: list[dict] = []
    for p in targets:
        for lang in tset.live.languages:
            s = service.suggest(p.draft, lang)
            suggestions.append(s)
            print(
                f"  [{len(suggestions)}] {p.source_node} {lang}: {s.status}", flush=True
            )
            if llm_adapter is not None:
                v = llm_adapter.judge_package(p.draft, lang)[0]
                templates.append(
                    {
                        "source_node": p.source_node,
                        "language": lang,
                        "total": v.total,
                        "accepted": v.accepted,
                        "rule_accepted": p.accepted,
                    }
                )
    seconds = time.perf_counter() - t0
    saved: dict[str, int] = {}
    with SqliteTransferStore(db_path) as store:
        for s in suggestions:
            outcome = store.save_suggestion(
                cycle_id, s.source_node, s.language, s.status, s.content_dict()
            )
            saved[outcome.action] = saved.get(outcome.action, 0) + 1

    def verdict(s, prefix: str) -> dict | None:  # noqa: ANN001
        return next((v for v in s.verdicts if str(v["judge"]).startswith(prefix)), None)

    rows = []
    for s in suggestions:
        rv, lv = verdict(s, "rule"), verdict(s, "llm")
        rows.append(
            {
                "source_node": s.source_node,
                "language": s.language,
                "status": s.status,
                "error": s.error,
                "raise": list(s.parsed.raise_ids) if s.parsed else [],
                "grounded": bool(s.check and s.check.grounding.grounded),
                "unsupported": list(s.check.grounding.unsupported) if s.check else [],
                "invented_ids": list(s.check.invented_ids) if s.check else [],
                "additions": list(s.check.additions) if s.check else [],
                "rule_total": rv["total"] if rv else None,
                "rule_accepted": bool(rv and rv["accepted"]),
                "llm_total": lv["total"] if lv else None,
                "llm_accepted": bool(lv and lv["accepted"]),
            }
        )
    gen_times = [s.seconds for s in suggestions if s.raw]
    judge_times = [r.seconds for r in (llm_adapter.results if llm_adapter else [])]
    return {
        "model": m.model,
        "llm_judge": bool(llm_adapter),
        "packages": [p.source_node for p in targets],
        "generated": len(suggestions),
        "parse_errors": sum(1 for s in suggestions if s.parsed is None),
        "grounded": sum(1 for r in rows if r["grounded"]),
        "invented_ids": sum(len(r["invented_ids"]) for r in rows),
        "additions": sum(len(r["additions"]) for r in rows),
        "rule_accepted": sum(1 for r in rows if r["rule_accepted"]),
        "llm_accepted": sum(1 for r in rows if r["llm_accepted"]),
        "accepted": sum(1 for s in suggestions if s.status == "accepted"),
        "templates": templates,
        "templates_llm_accepted": sum(1 for t in templates if t["accepted"]),
        "templates_combined": sum(
            1 for t in templates if t["accepted"] and t["rule_accepted"]
        ),
        "saved": saved,
        "rows": rows,
        "suggestions": [s.to_dict() for s in suggestions],
        "timings": {
            "suggest_avg_s": mean(gen_times),
            "judge_avg_s": mean(judge_times),
            "total_s": round(seconds, 1),
        },
        "tokens": {
            "prompt_avg": round(
                sum(s.prompt_tokens for s in suggestions) / len(suggestions)
            )
            if suggestions
            else None,
            "completion_avg": round(
                sum(s.completion_tokens for s in suggestions) / len(suggestions)
            )
            if suggestions
            else None,
        },
    }


def print_live(live: dict) -> None:
    n = live["generated"]
    print(
        f"live_suggestions: model={live['model']} think=off format=json packages={len(live['packages'])} "
        f"generated={n} parse_errors={live['parse_errors']} grounded={live['grounded']}/{n} "
        f"invented_ids={live['invented_ids']} additions={live['additions']} accepted={live['accepted']}/{n}"
    )
    if live["llm_judge"]:
        t = len(live["templates"])
        print(
            f"live_judge: suggestions rule={live['rule_accepted']}/{n} llm={live['llm_accepted']}/{n} "
            f"combined={live['accepted']}/{n} templates llm={live['templates_llm_accepted']}/{t} "
            f"combined={live['templates_combined']}/{t}"
        )
    else:
        print(
            f"live_judge: rule only, suggestions accepted={live['rule_accepted']}/{n}"
        )
    for r in live["rows"]:
        print(
            f"  {r['source_node']} {r['language']}: {r['status']} raise={','.join(r['raise']) or '-'} "
            f"rule={r['rule_total']} llm={r['llm_total']}"
            + (
                f" unsupported={','.join(r['unsupported'][:3])}"
                if r["unsupported"]
                else ""
            )
            + (f" invented={','.join(r['invented_ids'])}" if r["invented_ids"] else "")
            + (f" error={r['error'][:80]}" if r["error"] else "")
        )
    t = live["timings"]
    tok = live["tokens"]
    print(
        f"live_timings: suggest_avg_s={t['suggest_avg_s']} judge_avg_s={t['judge_avg_s']} "
        f"tokens_avg={tok['prompt_avg']}+{tok['completion_avg']} total_s={t['total_s']} "
        f"saved=" + ",".join(f"{k}:{v}" for k, v in live["saved"].items())
    )


if __name__ == "__main__":
    raise SystemExit(main())
