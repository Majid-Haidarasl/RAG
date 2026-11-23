#!/usr/bin/env python3
"""Phase 9: executor analysis & Issue-Knowledge-Executor (IKE) check.

Always (no Ollama needed):
* Loads the Phase 6 hierarchy, the executor registry
  (``data/executors/executor-registry.json``, from AR-EXE-023) and the
  Phase 7 issue registry; validates the executors.
* Matches executors to every sub-issue of AR-ISS-024 (and to each flat
  issue), compares the recommendations with the executors the team owner
  named in the issue registry and runs the referral-policy cases.
* Executor analysis: referrals per executor (lead / collaborator) and capacity.
* Issue-knowledge comparison with the Phase 8 retriever in lexical mode
  (node-scoped BM25): cited vs retrieved documents per sub-issue.
* Builds the IKE graph (registry-only and with retrieval), validates it and
  writes template summaries (Persian and English) that are fact-checked
  against the graph facts.

Live (only if local Ollama answers and bge-m3 + qwen3:8b are installed):
* Refreshes the Phase 8 index (``.rag-index/phase-08.sqlite``; only new or
  changed chunks are embedded), repeats the comparison with hybrid
  retrieval, and asks qwen3:8b (think off) for a Persian and an English
  summary of the IKE graph; both are fact-checked. Without Ollama the live
  step prints SKIPPED with the reason.

The overall status depends on pytest, the earlier steps and the offline
checks only; the live step is reported separately (live: ok/skipped/fail).
Prints the ``PHASE 9 SUMMARY`` block and writes
``results/phase-09/ike-check-<UTC>.json``.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
import traceback

ROOT_CANDIDATE = Path(__file__).resolve().parents[1]
_src = ROOT_CANDIDATE / "src"
if _src.is_dir() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from rag_core import __version__  # noqa: E402
from rag_core.executors.application.services import (  # noqa: E402
    ExecutorMatchingService,
    load_executor_registry,
    role_counts,
)
from rag_core.executors.domain.matching import ReferralPlan, ReferralRole  # noqa: E402
from rag_core.executors.infrastructure.hierarchy_acl import HierarchyTeamDirectory  # noqa: E402
from rag_core.executors.infrastructure.issues_acl import referral_requests  # noqa: E402
from rag_core.ike.application.services import IkeService, IkeSummaryService  # noqa: E402
from rag_core.ike.domain.model import IkeGraph, RelationType  # noqa: E402
from rag_core.ike.infrastructure.executors_acl import executor_names, referrals_by_item  # noqa: E402
from rag_core.ike.infrastructure.issues_acl import issue_view  # noqa: E402
from rag_core.ike.infrastructure.retrieval_acl import RetrieverKnowledgeSearch  # noqa: E402
from rag_core.issues.application.services import load_issue_registry  # noqa: E402
from rag_core.issues.infrastructure.hierarchy_acl import HierarchyOrgDirectory  # noqa: E402
from rag_core.qa.domain.fact_check import CitedFactValidator  # noqa: E402
from rag_core.rag.application.corpus import build_corpus_records  # noqa: E402
from rag_core.rag.application.indexing import IndexBuilder, build_retriever  # noqa: E402
from rag_core.rag.infrastructure.config import RagSettings, load_settings  # noqa: E402
from rag_core.rag.infrastructure.ollama import (  # noqa: E402
    OllamaChatModel,
    OllamaClient,
    OllamaEmbedder,
    OllamaError,
)
from rag_core.rag.infrastructure.sqlite_store import SqliteIndexStore  # noqa: E402

KIT = f"rag-core {__version__} (phase 9 executors + ike)"
SEPARATOR_START = "======== PHASE 9 SUMMARY ========"
SEPARATOR_END = "======== END PHASE 9 SUMMARY ========"
CASE = "AR-ISS-024"
TOP_K = 8

# Referral-policy cases (AR-EXE-023 §1 and §3): (item, executor, expected role).
POLICY_CASES = (
    ("AR-ISS-024/WEB", "EX-KIAN-RAZAVI", "excluded"),       # web team, but only one matching term
    ("AR-ISS-024/WEB", "EX-AMIN-TOURANI", "excluded"),      # matching terms, but not in the item's nodes
    ("AR-ISS-024/HW", "EX-ROOZBEH-MOHSENI", "excluded"),    # compatibility tests, but no shared knowledge
    ("AR-ISS-024/HW", "EX-KAMRAN-NIKPOUR", "excluded"),     # hardware deputy, sales is outside the domain
    ("AR-ISS-024/WIN", "EX-FARZANEH-JAVADI", "excluded"),   # holds AR-HW-015 but a single matching term
)
# AR-EXE-023 §3 names who serves which AR-ISS-024 sub-issue.
EXPECTED_LEADS = {
    "AR-ISS-024/HW": {"EX-SAEED-AKBARI", "EX-FARZANEH-JAVADI"},
    "AR-ISS-024/WIN": {"EX-ROOZBEH-MOHSENI"},
    "AR-ISS-024/LEG": {"EX-MAHSA-JALALI"},
}


def find_root(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.resolve()
    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents, ROOT_CANDIDATE]:
        if (candidate / "pyproject.toml").is_file() and (candidate / "data" / "executors").is_dir():
            return candidate
    raise SystemExit("could not find the repo root (pyproject.toml + data/executors/)")


def parse_prior(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in filter(None, (p.strip() for p in text.split(","))):
        name, _, code = part.partition("=")
        out[name.strip()] = code.strip() or "?"
    return out


def mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def comparison_metrics(comparisons: dict) -> dict:  # noqa: ANN001
    rows = list(comparisons.values())
    recalls = [c.cited_recall for c in rows if c.cited_recall is not None]
    return {
        "items": len(rows),
        "cited_recall_mean": mean(recalls),
        "covered": sum(len(c.covered) for c in rows),
        "cited": sum(len(c.cited) for c in rows),
        "suggested": sum(len(c.suggested) for c in rows),
        "missed": sum(len(c.missed) for c in rows),
        "cited_outside_scope": sum(len(c.outside_scope) for c in rows),
        "with_evidence": sum(1 for c in rows if c.evidence),
        "search_avg_s": mean([c.seconds for c in rows]),
        "per_item": [c.to_dict() for c in rows],
    }


def graph_summary(graph: IkeGraph) -> dict:
    return {"relations": len(graph.relations), "counts": graph.counts(), "endpoints": graph.endpoints(),
            "problems": graph.validate()}


def probe_ollama(settings: RagSettings) -> tuple[OllamaClient | None, str, dict]:
    info: dict[str, object] = {"base_url": settings.ollama.base_url}
    try:
        client = OllamaClient(settings.ollama.base_url, timeout_s=settings.ollama.generate_timeout_s,
                              retries=settings.ollama.retries)
        info["version"] = client.version(timeout=settings.ollama.connect_timeout_s)
        names = client.model_names(timeout=max(5.0, settings.ollama.connect_timeout_s))
    except OllamaError as exc:
        return None, f"Ollama not reachable at {settings.ollama.base_url} ({exc})", info
    info["models"] = names
    missing = [m for m in (settings.embedding.model, settings.generation.model) if not OllamaClient.has_model(names, m)]
    if missing:
        return None, "model(s) not installed: " + ", ".join(missing) + " (run: ollama pull " + " && ollama pull ".join(missing) + ")", info
    return client, "", info


def main() -> int:  # noqa: C901 - one linear report
    parser = argparse.ArgumentParser(description="Phase 9 executor analysis + IKE check.")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--no-live", action="store_true", help="skip the Ollama step")
    for name in ("passed", "failed", "errors", "skipped", "exit", "line"):
        parser.add_argument(f"--pytest-{name}", default=None)
    parser.add_argument("--python-version", default=None)
    parser.add_argument("--prior", default="", help="earlier steps as name=exit,...")
    args = parser.parse_args()

    root = find_root(args.root)
    settings = load_settings(args.config or root / "config" / "rag.yaml")
    out_dir = args.out or root / "results" / "phase-09"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_json = out_dir / f"ike-check-{stamp}.json"
    t0 = time.perf_counter()

    # ---- registries
    teams = HierarchyTeamDirectory.from_registry(root / "data" / "registry")
    org = HierarchyOrgDirectory.from_registry(root / "data" / "registry")
    loaded = load_executor_registry(root / "data" / "executors", teams)
    executors = loaded.executors
    issues = load_issue_registry(root / "data" / "issues", org).issues
    repo = loaded.repository()
    matching = ExecutorMatchingService(repo)

    # ---- matching
    case = next((i for i in issues if str(i.identifier) == CASE), None)
    case_plans: list[ReferralPlan] = matching.plans(referral_requests(case)) if case is not None and executors else []
    flat_plans: list[ReferralPlan] = []
    if executors:
        for issue in issues:
            if not issue.subissues:
                flat_plans.extend(matching.plans(referral_requests(issue)))
    seeds = [matching.compare_with_seed(p) for p in case_plans]
    tp = sum(s.true_positives for s in seeds)
    named = sum(len(s.resolved) for s in seeds)
    recommended = sum(len(s.recommended) for s in seeds)
    unresolved = [n for s in seeds for n in s.unresolved]
    plan_by_item = {p.request.item_id: p for p in case_plans}
    policy = []
    for item, executor_id, expected in POLICY_CASES:
        plan = plan_by_item.get(item)
        role = plan.match_for(executor_id).role.value if plan is not None else "missing"
        policy.append({"item": item, "executor": executor_id, "expected": expected, "role": role, "ok": role == expected})
    leads_ok = bool(case_plans) and all(
        (plan_by_item[i].lead is not None and plan_by_item[i].lead.executor_id in allowed)
        for i, allowed in EXPECTED_LEADS.items() if i in plan_by_item
    )
    load = matching.load(case_plans)

    # ---- issue-knowledge comparison (offline, lexical) and IKE graphs
    corpus = build_corpus_records(root)
    lexical = build_retriever(corpus.records, scope=corpus.scope, config=settings.retrieval)
    view = issue_view(case) if case is not None else None
    referrals = referrals_by_item(case_plans, executors)
    names = executor_names(executors)
    validator = CitedFactValidator()
    offline_ike = IkeService(RetrieverKnowledgeSearch(lexical, corpus.scope), top_k=TOP_K,
                             min_lexical=settings.qa.evidence_min_lexical, min_vector=settings.qa.evidence_min_vector)
    graph_error = ""
    registry_graph = offline_graph = None
    offline_cmp: dict = {}
    try:
        if view is not None:
            registry_graph = IkeService().build(view, referrals)
            offline_cmp = offline_ike.compare(view)
            offline_graph = offline_ike.build(view, referrals, offline_cmp)
    except Exception as exc:  # noqa: BLE001 - reported as a failed check
        graph_error = f"{type(exc).__name__}: {exc}"
    summaries = IkeSummaryService(validator)
    template = {}
    facts: list[str] = []
    if view is not None and offline_graph is not None:
        facts = summaries.facts(view, offline_graph, names)
        template = {lang: summaries.template(view, offline_graph, names, lang) for lang in ("fa", "en")}

    # ---- live step
    live: dict[str, object] = {"status": "skipped", "reason": "disabled with --no-live"}
    ollama_info: dict[str, object] = {"base_url": settings.ollama.base_url}
    if not args.no_live and view is not None and offline_graph is not None:
        client, reason, ollama_info = probe_ollama(settings)
        if client is None:
            live = {"status": "skipped", "reason": reason}
        else:
            print("live step: Ollama", ollama_info.get("version"), "→ hybrid comparison and IKE summaries", flush=True)
            try:
                live = {"status": "ok", **live_step(root, settings, corpus, client, view, referrals, names, validator)}
            except Exception as exc:  # noqa: BLE001 - the live step never breaks the kit status
                live = {"status": "fail", "reason": f"{type(exc).__name__}: {exc}",
                        "traceback": traceback.format_exc(limit=5)}
    elif not args.no_live:
        live = {"status": "skipped", "reason": "offline IKE graph not available"}
    total_s = time.perf_counter() - t0

    # ---- checks
    prior = parse_prior(args.prior)
    reg_counts = registry_graph.counts() if registry_graph is not None else {}
    subs = list(view.sub_items) if view is not None else []
    checks = {
        "pytest": args.pytest_exit in (None, "0", 0),
        "prior_steps": all(v == "0" for v in prior.values()),
        "executor_registry_valid": loaded.report.ok and len(executors) == 15,
        "seed_executors_resolved": bool(seeds) and not unresolved,
        "matching_matches_seed": bool(seeds) and all(s.agrees for s in seeds),
        "referral_policy": bool(policy) and all(p["ok"] for p in policy),
        "leads_match_exe023": leads_ok,
        "records_built": bool(corpus.records) and not corpus.failures,
        "ike_graph_valid": not graph_error and registry_graph is not None and offline_graph is not None
                           and not registry_graph.validate() and not offline_graph.validate(),
        "ike_graph_consistent": registry_graph is not None
                                and reg_counts.get("part_of") == len(subs)
                                and reg_counts.get("depends_on") == sum(len(s.depends_on) for s in subs)
                                and reg_counts.get("can_handle") == recommended,
        "template_summaries_grounded": bool(template) and all(s.check.grounded for s in template.values())
                                       and all(len(s.check.mentioned) == len(subs) for s in template.values()),
    }
    status = "PASS" if all(checks.values()) else "FAIL"

    flat_rows = [{"item_id": p.request.item_id, "owner": p.request.owner_node,
                  "lead": p.lead.executor_id if p.lead else None,
                  "collaborators": [m.executor_id for m in p.collaborators]} for p in flat_plans]
    payload = {
        "kit": KIT,
        "run_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": status,
        "checks": checks,
        "python": args.python_version,
        "pytest": {"passed": args.pytest_passed, "failed": args.pytest_failed, "errors": args.pytest_errors,
                   "skipped": args.pytest_skipped, "exit": args.pytest_exit, "result_line": args.pytest_line},
        "prior_steps": prior,
        "models": {"embedding": settings.embedding.model, "generation": settings.generation.model,
                   "think": settings.generation.think, "options": settings.generation.options},
        "ollama": ollama_info,
        "executors": {
            "total": len(executors),
            "validation": {"errors": [str(e) for e in loaded.report.errors],
                           "warnings": [str(w) for w in loaded.report.warnings]},
            "capacity_published": sum(1 for e in executors if e.capacity.is_published),
            "capacity_unpublished": sum(1 for e in executors if not e.capacity.is_published),
            "home_nodes": sorted({str(e.home_node) for e in executors}),
            "load": [row.to_dict() for row in load],
        },
        "matching": {
            "case": CASE,
            "plans": [p.to_dict() for p in case_plans],
            "seed": [s.to_dict() for s in seeds],
            "precision": round(tp / recommended, 4) if recommended else None,
            "recall": round(tp / named, 4) if named else None,
            "roles": role_counts(case_plans),
            "policy": policy,
            "flat_issues": flat_rows,
        },
        "knowledge_offline": comparison_metrics(offline_cmp),
        "ike": {
            "registry_graph": graph_summary(registry_graph) if registry_graph is not None else None,
            "offline_graph": offline_graph.to_dict() if offline_graph is not None else None,
            "error": graph_error,
            "facts": facts,
            "template_summaries": {k: v.to_dict() for k, v in template.items()},
        },
        "live": live,
        "total_seconds": round(total_s, 2),
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- summary block
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
    ex = payload["executors"]
    print(f"executors: total={ex['total']} home_nodes={len(ex['home_nodes'])} capacity_published={ex['capacity_published']} "
          f"unpublished={ex['capacity_unpublished']} validation_errors={len(loaded.report.errors)} "
          f"warnings={len(loaded.report.warnings)}")
    for e in loaded.report.errors[:10]:
        print(f"  - {e}")
    m = payload["matching"]
    print(f"matching: case={CASE} sub_issues={len(case_plans)} recommended={recommended} named={named} "
          f"seed_agreement={sum(1 for s in seeds if s.agrees)}/{len(seeds)} precision={m['precision']} recall={m['recall']}")
    for p in case_plans:
        lead = p.lead
        collab = ",".join(c.display_name for c in p.collaborators) or "-"
        seed = next((s for s in seeds if s.item_id == p.request.item_id), None)
        print(f"  {p.request.item_id}: lead={lead.display_name if lead else '-'} collab={collab} "
              f"authority={p.request.acceptance_authority} seed={'ok' if seed and seed.agrees else 'MISMATCH'}")
    print("referral_roles: " + " ".join(f"{k}={v}" for k, v in m["roles"].items()))
    print("referral_policy: " + " ".join(f"{p['executor']}@{p['item'].split('/')[1]}={p['role']}"
                                         f"{'' if p['ok'] else '(MISMATCH)'}" for p in policy))
    busy = [row for row in load if row.referrals]
    print(f"executor_load: with_referrals={len(busy)}/{len(load)} "
          + " ".join(f"{row.executor_id}={len(row.lead)}L+{len(row.collaborator)}C" for row in busy))
    print(f"flat_issue_matching: issues={len(flat_plans)} with_lead={sum(1 for p in flat_plans if p.lead)}")
    ko = payload["knowledge_offline"]
    print(f"knowledge_offline: mode=lexical items={ko['items']} cited_recall@{TOP_K}={ko['cited_recall_mean']} "
          f"covered={ko['covered']}/{ko['cited']} suggested={ko['suggested']} cited_outside_scope={ko['cited_outside_scope']} "
          f"with_evidence={ko['with_evidence']}/{ko['items']}")
    if registry_graph is not None:
        print("ike_registry_graph: relations=" + str(len(registry_graph.relations)) + " "
              + " ".join(f"{k}={v}" for k, v in registry_graph.counts().items()))
    if offline_graph is not None:
        print("ike_offline_graph: relations=" + str(len(offline_graph.relations)) + " "
              + " ".join(f"{k}={v}" for k, v in offline_graph.counts().items()))
        lacks = offline_graph.of_type(RelationType.KNOWLEDGE_LACK)
        print("knowledge_lacks: " + (" ".join(f"{r.source_id.split('/')[-1]}->{r.target_id}" for r in lacks) or "none"))
    if graph_error:
        print(f"ike_error: {graph_error}")
    if template:
        print("summary_template: " + " ".join(
            f"{k}=grounded:{v.check.grounded} coverage={v.check.coverage} claims={v.check.claims}" for k, v in template.items()))
    print(f"live: {live['status']}" + (f" ({live.get('reason')})" if live.get("reason") else ""))
    if live["status"] == "ok":
        ix = live["index"]  # type: ignore[index]
        kl = live["knowledge"]  # type: ignore[index]
        print(f"live_index: active={ix['active']} embedded={ix['embedded']} reused={ix['reused']} dim={ix['dim']} "
              f"build_s={ix['seconds']}")
        print(f"live_knowledge: mode=hybrid cited_recall@{TOP_K}={kl['cited_recall_mean']} covered={kl['covered']}/{kl['cited']} "
              f"suggested={kl['suggested']} with_evidence={kl['with_evidence']}/{kl['items']} search_avg_s={kl['search_avg_s']}")
        print("live_graph: relations=" + str(live["graph"]["relations"]) + " "  # type: ignore[index]
              + " ".join(f"{k}={v}" for k, v in live["graph"]["counts"].items()))  # type: ignore[index,union-attr]
        for lang, s in live["summaries"].items():  # type: ignore[union-attr]
            print(f"live_summary_{lang}: grounded={s['check']['grounded']} unsupported={len(s['check']['unsupported'])} "
                  f"coverage={s['check']['coverage']} chars={len(s['text'])} gen_s={s['seconds']} "
                  f"tokens={s['prompt_tokens']}+{s['completion_tokens']}")
        print(f"live_timings: total_s={round(total_s, 1)}")
    print("checks: " + " ".join(f"{k}={'ok' if v else 'FAIL'}" for k, v in checks.items()))
    print(f"results_json: {out_json}")
    print(SEPARATOR_END)
    return 0 if status == "PASS" else 1


def live_step(root: Path, settings: RagSettings, corpus, client: OllamaClient, view, referrals,  # noqa: ANN001
              names, validator) -> dict:  # noqa: ANN001
    embedder = OllamaEmbedder(client, settings.embedding.model, settings.embedding.batch_size,
                              settings.embedding.num_ctx, settings.ollama.keep_alive, settings.ollama.embed_timeout_s)
    with SqliteIndexStore(root / settings.index.path) as store:
        def progress(done: int, total: int) -> None:
            if done == total or done % (settings.embedding.batch_size * 10) == 0:
                print(f"  embedded {done}/{total}", flush=True)

        build = IndexBuilder(store, embedder, settings.embedding.model, settings.embedding.batch_size).refresh(
            corpus.records, progress)
        vectors = store.load_vectors(settings.embedding.model)
    if vectors.dim != settings.embedding.dim:
        raise OllamaError(f"embedding dim {vectors.dim} != configured {settings.embedding.dim}")
    hybrid = build_retriever(corpus.records, vectors=vectors, embedder=embedder, scope=corpus.scope,
                             config=settings.retrieval)
    ike = IkeService(RetrieverKnowledgeSearch(hybrid, corpus.scope), top_k=TOP_K,
                     min_lexical=settings.qa.evidence_min_lexical, min_vector=settings.qa.evidence_min_vector)
    comparisons = ike.compare(view)
    graph = ike.build(view, referrals, comparisons)
    chat = OllamaChatModel(client, settings.generation.model, dict(settings.generation.options),
                           settings.generation.think, settings.ollama.keep_alive, settings.ollama.generate_timeout_s)
    service = IkeSummaryService(validator, chat)
    summaries = {}
    for lang in ("fa", "en"):
        print(f"  summary {lang} ...", flush=True)
        summaries[lang] = service.generate(view, graph, names, lang).to_dict()
    # The fact lines the summaries were written from; Phase 10 judges the summaries against them.
    return {"index": build.to_dict(), "knowledge": comparison_metrics(comparisons), "graph": graph_summary(graph),
            "graph_relations": [r.to_dict() for r in graph.relations], "summaries": summaries,
            "facts": service.facts(view, graph, names)}


if __name__ == "__main__":
    raise SystemExit(main())
