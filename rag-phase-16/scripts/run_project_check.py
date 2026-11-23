#!/usr/bin/env python3
"""Phase 12: project, research, achievement and gap tracking + key-issue prioritization.

Always (no Ollama needed):
* Loads the layer / node registry (Phase 6), the active corpus documents
  (Phase 4/5), the issues (Phase 7), the executors and the offline IKE graph
  of AR-ISS-024 (Phase 9: leads and knowledge lacks) and the project registry
  (data/projects/project-registry.json: projects, achievements, challenges,
  research gaps, unsolved issues and the interim knowledge scorecard).
* Validates the registry (nodes, documents, issues, record rules, project
  status against the linked issues) and grounds it in the corpus: project
  numbers and every record statement must be found in the cited documents,
  in Persian and in English.
* Runs the research-gap rules (config/projects.yaml) and ranks the open
  issues with the weighted, explainable priority score; checks the ranking
  against weight changes and compares it with the Phase 7 formula.
* Builds the key-issue brief (Persian + English template) and judges it with
  the Phase 10 rule judge (18/20); broken copies of the brief and of the
  registry must be rejected (negative controls).
* Exports CSVs (exports/project-tracking/<cycle>/) and reads them back.

Live (only if local Ollama answers and qwen3:8b is installed):
* AI key-issue brief (qwen3:8b, think off, JSON) in Persian and English,
  fact-checked and judged by qwen3:8b and the rule judge together (combined
  judge). Advice only: the deterministic ranking never changes.
  Without Ollama: live SKIPPED.

The status depends on pytest, the earlier steps and the offline checks only.
Prints the ``PHASE 12 SUMMARY`` block and writes
``results/phase-12/project-check-<UTC>.json``.
"""

from __future__ import annotations

import argparse
import copy
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
from rag_core.executors.application.services import ExecutorMatchingService, load_executor_registry  # noqa: E402
from rag_core.executors.infrastructure.hierarchy_acl import HierarchyTeamDirectory  # noqa: E402
from rag_core.executors.infrastructure.issues_acl import referral_requests  # noqa: E402
from rag_core.hierarchy.application.workflows import load_and_validate  # noqa: E402
from rag_core.ike.application.services import IkeService  # noqa: E402
from rag_core.ike.domain.summary import digest  # noqa: E402
from rag_core.ike.infrastructure.executors_acl import referrals_by_item  # noqa: E402
from rag_core.ike.infrastructure.issues_acl import issue_view  # noqa: E402
from rag_core.ike.infrastructure.retrieval_acl import RetrieverKnowledgeSearch  # noqa: E402
from rag_core.issues.application.services import load_issue_registry  # noqa: E402
from rag_core.issues.infrastructure.hierarchy_acl import HierarchyOrgDirectory  # noqa: E402
from rag_core.judging.application.services import LlmJudge, judge_all  # noqa: E402
from rag_core.judging.domain.rule_judge import RuleBasedJudge  # noqa: E402
from rag_core.judging.infrastructure.config import JudgeSettings, load_judge_settings  # noqa: E402
from rag_core.judging.infrastructure.prompt_yaml import load_judge_prompts, load_rubric  # noqa: E402
from rag_core.prioritization.application.services import PrioritizationService, explain  # noqa: E402
from rag_core.prioritization.domain.advice import (  # noqa: E402
    AdviceParseError,
    AiBrief,
    advice_prompt,
    check_advice,
    parse_advice,
)
from rag_core.prioritization.domain.brief import BriefGap, KeyIssueBrief, build_brief  # noqa: E402
from rag_core.prioritization.domain.scoring import PriorityScorer  # noqa: E402
from rag_core.prioritization.infrastructure.judging_acl import (  # noqa: E402
    BriefJudge,
    negative_brief_cases,
    verdict_dict,
)
from rag_core.prioritization.infrastructure.signals_acl import exposure_by_issue, issue_signals, sub_tasks  # noqa: E402
from rag_core.projects.application.services import ProjectTrackingService  # noqa: E402
from rag_core.projects.domain.evidence import ground_registry  # noqa: E402
from rag_core.projects.domain.model import RecordKind  # noqa: E402
from rag_core.projects.domain.validation import RegistryValidator  # noqa: E402
from rag_core.projects.infrastructure.config import ProjectSettings, load_project_settings  # noqa: E402
from rag_core.projects.infrastructure.corpus_acl import document_texts  # noqa: E402
from rag_core.projects.infrastructure.csv_export import export_tables, round_trip_problems  # noqa: E402
from rag_core.projects.infrastructure.issues_acl import issue_facts  # noqa: E402
from rag_core.projects.infrastructure.registry_json import read_registry_dict, registry_from_dict  # noqa: E402
from rag_core.qa.domain.fact_check import CitedFactValidator, source_numbers  # noqa: E402
from rag_core.rag.application.corpus import build_corpus_records  # noqa: E402
from rag_core.rag.application.indexing import build_retriever  # noqa: E402
from rag_core.rag.infrastructure.config import RagSettings, load_settings  # noqa: E402
from rag_core.rag.infrastructure.ollama import OllamaChatModel, OllamaClient, OllamaError  # noqa: E402
from rag_core.research_gaps.application.services import GapReport, GapService  # noqa: E402
from rag_core.research_gaps.domain.rules import GapRuleBook  # noqa: E402
from rag_core.research_gaps.infrastructure.inputs_acl import build_inputs, ike_items  # noqa: E402
from rag_core.shared_kernel.errors import DomainError  # noqa: E402
from rag_core.transfer.infrastructure.sources_acl import document_versions  # noqa: E402

KIT = f"rag-core {__version__} (phase 12 projects, research gaps, prioritization)"
SEPARATOR_START = "======== PHASE 12 SUMMARY ========"
SEPARATOR_END = "======== END PHASE 12 SUMMARY ========"
TOP_K = 8
LANGS = ("fa", "en")


def find_root(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.resolve()
    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents, ROOT_CANDIDATE]:
        if (candidate / "pyproject.toml").is_file() and (candidate / "config" / "projects.yaml").is_file():
            return candidate
    raise SystemExit("could not find the repo root (pyproject.toml + config/projects.yaml)")


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


def mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 3) if values else None


def ike_digest(root: Path, settings: RagSettings, corpus, org, issues, case_id: str):  # noqa: ANN001, ANN201
    """Phase 9 offline IKE graph of the case -> digest (leads and knowledge lacks per sub-issue)."""
    teams = HierarchyTeamDirectory(org)
    loaded = load_executor_registry(root / "data" / "executors", teams)
    executors = loaded.executors
    case = next((i for i in issues if str(i.identifier) == case_id), None)
    if case is None or not executors:
        raise RuntimeError(f"{case_id} or the executor registry is missing")
    plans = ExecutorMatchingService(loaded.repository()).plans(referral_requests(case))
    view = issue_view(case)
    lexical = build_retriever(corpus.records, scope=corpus.scope, config=settings.retrieval)
    ike = IkeService(RetrieverKnowledgeSearch(lexical, corpus.scope), top_k=TOP_K,
                     min_lexical=settings.qa.evidence_min_lexical, min_vector=settings.qa.evidence_min_vector)
    graph = ike.build(view, referrals_by_item(plans, executors), ike.compare(view))
    return digest(view, graph), executors


def probe_ollama(settings: RagSettings, model: str) -> tuple[OllamaClient | None, str, dict]:
    info: dict[str, object] = {"base_url": settings.ollama.base_url}
    try:
        client = OllamaClient(settings.ollama.base_url, timeout_s=settings.ollama.generate_timeout_s,
                              retries=settings.ollama.retries)
        info["version"] = client.version(timeout=settings.ollama.connect_timeout_s)
        names = client.model_names(timeout=max(5.0, settings.ollama.connect_timeout_s))
    except OllamaError as exc:
        return None, f"Ollama not reachable at {settings.ollama.base_url} ({exc})", info
    info["models"] = names
    if not OllamaClient.has_model(names, model):
        return None, f"model not installed: {model} (run: ollama pull {model})", info
    return client, "", info


# ---- registry negative controls ---------------------------------------------------------
def _find(items: list[dict], item_id: str) -> dict:
    return next(i for i in items if i["id"] == item_id)


def registry_mutations(raw: dict) -> list[tuple[str, dict]]:
    """Broken copies of the shipped registry. Each one must be rejected."""
    out: list[tuple[str, dict]] = []

    def mutate(kind: str, change) -> None:  # noqa: ANN001
        data = copy.deepcopy(raw)
        try:
            change(data)
        except (KeyError, StopIteration, IndexError):
            return
        out.append((kind, data))

    mutate("fabricated_document", lambda d: _find(d["records"], "ACH-IKE-PATH")["evidence"].append("AR-XYZ-999"))
    mutate("unknown_node", lambda d: d["projects"][0].__setitem__("owner_node", "N-XXX"))
    mutate("unknown_issue", lambda d: _find(d["records"], "UNS-AZP-DELAY").__setitem__("issues", ["AR-ISS-099"]))
    mutate("wrong_number", lambda d: _find(d["projects"], "PRJ-RHS-PORTAL").__setitem__("progress_percent", 87))
    mutate("research_claims_result",
           lambda d: _find(d["records"], "RES-PHOTO-TRIAGE").__setitem__("validated_result", True))
    mutate("achievement_without_evidence",
           lambda d: _find(d["records"], "ACH-COMMIT-SPLIT").__setitem__("evidence", []))
    mutate("unsolved_without_issue", lambda d: _find(d["records"], "UNS-AZP-RECEIVABLE").__setitem__("issues", []))
    mutate("lesson_without_conditions",
           lambda d: _find(d["records"], "CHL-REPAIR-NOTES").__setitem__("conditions", ""))
    mutate("wrong_status", lambda d: _find(d["projects"], "PRJ-DSP-VISITOR").__setitem__("status", "at_risk"))
    return out


def registry_rejects(data: dict, validator: RegistryValidator, texts, fact_validator) -> tuple[bool, str]:  # noqa: ANN001
    try:
        registry = registry_from_dict(data)
    except (DomainError, ValueError, KeyError) as exc:
        return True, f"load:{type(exc).__name__}"
    problems = validator.validate(registry)
    if problems:
        return True, str(problems[0])
    evidence = ground_registry(registry, texts, fact_validator, source_numbers)
    if not evidence.ok:
        bad = evidence.failures()[0]
        return True, f"evidence:{bad.ref}/{bad.language}"
    return False, "accepted"


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 12 project, research and gap tracking + prioritization.")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--config", type=Path, default=None, help="config/rag.yaml (Ollama endpoint)")
    parser.add_argument("--judge-config", type=Path, default=None, help="config/judge.yaml")
    parser.add_argument("--project-config", type=Path, default=None, help="config/projects.yaml")
    parser.add_argument("--out", type=Path, default=None, help="folder for project-check-*.json")
    parser.add_argument("--exports", type=Path, default=None, help="CSV folder (default from config/projects.yaml)")
    parser.add_argument("--no-live", action="store_true", help="skip the Ollama step")
    for name in ("passed", "failed", "errors", "skipped", "exit", "line"):
        parser.add_argument(f"--pytest-{name}", default=None)
    parser.add_argument("--python-version", default=None)
    parser.add_argument("--prior", default="", help="earlier steps as name=exit,...")
    args = parser.parse_args()

    root = find_root(args.root)
    settings = load_settings(args.config or root / "config" / "rag.yaml")
    jset: JudgeSettings = load_judge_settings(args.judge_config or root / "config" / "judge.yaml")
    pset: ProjectSettings = load_project_settings(args.project_config or root / "config" / "projects.yaml")
    out_dir = args.out or root / "results" / "phase-12"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_json = out_dir / f"project-check-{stamp}.json"
    csv_dir = args.exports or root / pset.storage.csv_dir
    cycle_id, cutoff = pset.cycle.id, pset.cycle.cutoff
    t0 = time.perf_counter()
    errors: list[str] = []

    # ---- registry, corpus, issues, IKE, project registry
    loaded = load_and_validate(root / "data" / "registry")
    org = loaded.organization
    corpus = build_corpus_records(root)
    versions = document_versions(corpus.records)
    texts = document_texts(corpus.records, versions)
    issues: list = []
    executors: list = []
    ike = None
    if org is None:
        errors.append(f"registry invalid: {len(loaded.report.errors)} error(s)")
    else:
        loaded_issues = load_issue_registry(root / "data" / "issues", HierarchyOrgDirectory(org))
        issues = list(loaded_issues.issues)
        if not issues:
            errors.append("issues: the issue registry did not load")
        else:
            try:
                ike, executors = ike_digest(root, settings, corpus, org, issues, pset.case)
            except Exception as exc:  # noqa: BLE001 - reported as a failed check
                errors.append(f"ike: {type(exc).__name__}: {exc}")
    raw_registry: dict = {}
    registry = None
    try:
        raw_registry = read_registry_dict(root / pset.storage.registry_dir)
        registry = registry_from_dict(raw_registry)
    except Exception as exc:  # noqa: BLE001 - reported as a failed check
        errors.append(f"projects: {type(exc).__name__}: {exc}")

    nodes = {str(n.identifier) for n in org.all_nodes()} if org is not None else set()
    facts_by_issue = issue_facts(issues)
    pr = pset.prioritization
    validator = RegistryValidator(nodes, set(versions), facts_by_issue, risk_threshold=pr.risk_threshold)
    fact_validator = CitedFactValidator()

    problems: list = []
    evidence = None
    overview: list = []
    matrix: dict = {}
    report = GapReport()
    result = None
    briefs: dict[str, KeyIssueBrief] = {}
    brief_results: dict[str, object] = {}
    rubric = load_rubric(root / jset.files.rubric)
    rule_judge = RuleBasedJudge(rubric, fact_validator, jset.rules)
    rule_brief = BriefJudge(rule_judge)
    neg_registry: list[dict] = []
    neg_brief: list = []
    csv_info: dict[str, object] = {}
    tables: dict[str, list[dict]] = {}
    signals: list = []
    if registry is not None and org is not None and issues:
        problems = validator.validate(registry)
        evidence = ground_registry(registry, texts, fact_validator, source_numbers)
        tracking = ProjectTrackingService(registry, facts_by_issue, risk_threshold=pr.risk_threshold)
        overview = tracking.overview()
        matrix = tracking.matrix()

        # ---- research-gap rules
        report = GapService(GapRuleBook(pset.gap_rules)).detect(build_inputs(registry, issues, ike_items(ike)))

        # ---- prioritization
        signals = issue_signals(issues, report.count_by_issue(), exposure_by_issue(registry.projects))
        scorer = PriorityScorer(pr.weights, pr.caps, key_count=pr.key_count, key_min_score=pr.key_min_score)
        result = PrioritizationService(scorer, pr.sensitivity_ratios).run(signals, sub_tasks(issues))

        # ---- key-issue brief (template) + rule judge
        key = [r for r in result.ranking.ranked if r.key]
        gap_rows = [BriefGap(g.gap_id, g.subject, g.severity.value, g.title_en, g.title_fa, g.issue_id)
                    for g in report.gaps if g.issue_id]
        research_rows = [BriefGap(g.gap_id, g.subject, g.severity.value, g.title_en, g.title_fa)
                         for g in report.gaps if g.rule == "RG"]
        for lang in LANGS:
            b = build_brief(cycle_id, cutoff, key, gap_rows, research_rows, result.next_actions, lang,
                            tuple(result.ranking.order))
            briefs[lang] = b
            brief_results[lang] = rule_brief.judge_brief(b)

        # ---- negative controls
        for kind, data in registry_mutations(raw_registry):
            rejected, why = registry_rejects(data, validator, texts, fact_validator)
            neg_registry.append({"kind": kind, "rejected": rejected, "reason": why})
        cases = [c for b in briefs.values() for c in negative_brief_cases(b)]
        neg_brief = judge_all(rule_judge, cases)

        # ---- CSV export
        tables = {
            "projects": [o.to_dict() for o in overview],
            "records": [{"record_id": r.record_id, "kind": r.kind.value, "state": r.state.value,
                         "project": r.project, "title_en": r.title_en, "title_fa": r.title_fa,
                         "issues": list(r.issues), "nodes": list(r.nodes), "evidence": list(r.evidence),
                         "conditions": r.conditions} for r in registry.records],
            "gaps": [g.to_dict() for g in report.gaps],
            "priorities": [{"rank": s.rank, "issue_id": s.issue_id, "score": s.score, "key": s.key,
                            "top_factors": [k for k, _ in s.top_factors()], "title_en": s.title_en,
                            "title_fa": s.title_fa} for s in result.ranking.ranked],
        }
        try:
            files = export_tables(tables, csv_dir, cycle_id)
            csv_info = {"dir": rel(root, csv_dir / cycle_id), "files": len(files),
                        "problems": round_trip_problems(tables, csv_dir, cycle_id)}
        except Exception as exc:  # noqa: BLE001 - reported as a failed check
            errors.append(f"csv: {type(exc).__name__}: {exc}")
            csv_info = {"error": f"{type(exc).__name__}: {exc}"}

    # ---- live step
    live: dict[str, object] = {"status": "skipped", "reason": "disabled with --no-live"}
    ollama_info: dict[str, object] = {"base_url": settings.ollama.base_url}
    if not args.no_live:
        if not briefs:
            live = {"status": "skipped", "reason": "no key-issue brief to work on"}
        else:
            client, reason, ollama_info = probe_ollama(settings, pset.model.model)
            if client is None:
                live = {"status": "skipped", "reason": reason}
            else:
                print("live step: Ollama", ollama_info.get("version"), "-> qwen3:8b key-issue brief and judge",
                      flush=True)
                try:
                    live = {"status": "ok", **live_step(pset, jset, client, rubric, root, rule_judge,
                                                        fact_validator, briefs)}
                except Exception as exc:  # noqa: BLE001 - the live step never breaks the kit status
                    live = {"status": "fail", "reason": f"{type(exc).__name__}: {exc}",
                            "traceback": traceback.format_exc(limit=5)}
    total_s = time.perf_counter() - t0

    # ---- checks
    prior = parse_prior(args.prior)
    ranking = result.ranking if result else None
    key_ids = ranking.key_ids if ranking else []
    open_research = [r.record_id for r in registry.records_of(RecordKind.RESEARCH) if r.state.value != "recorded"] \
        if registry is not None else []
    rg_subjects = {g.subject for g in report.gaps if g.rule == "RG"}
    gap_ids = [g.gap_id for g in report.gaps]
    neg_brief_rejected = sum(1 for r in neg_brief if not r.accepted)
    neg_registry_rejected = sum(1 for r in neg_registry if r["rejected"])
    sens = result.sensitivity if result else None
    checks = {
        "pytest": args.pytest_exit in (None, "0", 0),
        "prior_steps": all(v == "0" for v in prior.values()),
        "registry_loaded": org is not None and bool(issues) and registry is not None and ike is not None
        and not any(e.startswith(("registry", "issues", "ike", "projects")) for e in errors),
        "records_built": bool(corpus.records) and not corpus.failures,
        "registry_valid": registry is not None and not problems,
        "evidence_grounded": evidence is not None and evidence.ok,
        "research_gaps_tracked": bool(open_research) and set(open_research) <= rg_subjects,
        "gaps_detected": bool(gap_ids) and len(gap_ids) == len(set(gap_ids)),
        "ranking_complete": ranking is not None and bool(ranking.ranked)
        and len(ranking.ranked) + len(ranking.excluded) == len(issues),
        "key_issues_selected": bool(key_ids) and len(key_ids) <= pr.key_count and ranking is not None
        and key_ids[0] == ranking.order[0] and all(ranking.get(k).score >= pr.key_min_score for k in key_ids),  # type: ignore[union-attr]
        "ranking_stable": sens is not None and sens.perturbations > 0 and sens.top1_stable == sens.perturbations,
        "brief_accepted": len(brief_results) == len(LANGS) and all(r.accepted for r in brief_results.values()),  # type: ignore[attr-defined]
        "negative_controls_rejected": bool(neg_brief) and bool(neg_registry)
        and neg_brief_rejected == len(neg_brief) and neg_registry_rejected == len(neg_registry),
        "csv_round_trip": bool(csv_info.get("files")) and not csv_info.get("problems"),
    }
    status = "PASS" if all(checks.values()) else "FAIL"

    counts = registry.counts_by_kind() if registry is not None else {}
    payload = {
        "kit": KIT,
        "run_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": status,
        "checks": checks,
        "errors": errors,
        "python": args.python_version,
        "pytest": {"passed": args.pytest_passed, "failed": args.pytest_failed, "errors": args.pytest_errors,
                   "skipped": args.pytest_skipped, "exit": args.pytest_exit, "result_line": args.pytest_line},
        "prior_steps": prior,
        "cycle": {"id": cycle_id, "cutoff": cutoff},
        "registry": {"projects": len(registry.projects) if registry else 0,
                     "records": len(registry.records) if registry else 0, "by_kind": counts,
                     "scorecard": len(registry.scorecard) if registry else 0,
                     "problems": [p.__dict__ for p in problems]},
        "evidence": evidence.to_dict() if evidence else None,
        "projects": [o.to_dict() for o in overview],
        "matrix": matrix,
        "gaps": report.to_dict(),
        "prioritization": result.to_dict() if result else None,
        "briefs": {lang: {"text": b.text, "facts": list(b.facts), "items": list(b.items), "gaps": list(b.gaps),
                          "words": b.words, "rule": verdict_dict(brief_results[lang])}  # type: ignore[arg-type]
                   for lang, b in briefs.items()},
        "negative_controls": {"registry": neg_registry,
                              "brief": [{"case_id": r.case_id, "origin": r.origin, "accepted": r.accepted,
                                         "total": r.total} for r in neg_brief]},
        "csv": csv_info,
        "ollama": ollama_info,
        "live": live,
        "timings": {"total_s": round(total_s, 2), "corpus_s": round(corpus.seconds, 2)},
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

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
    print(f"cycle: {cycle_id} cutoff={cutoff} case={pset.case} ike_items={len(ike.items) if ike else 0} "
          f"executors={len(executors)}")
    if registry is not None:
        print(f"registry: projects={len(registry.projects)} records={len(registry.records)} ("
              + " ".join(f"{k}={v}" for k, v in counts.items()) + f") scorecard={len(registry.scorecard)} "
              f"problems={len(problems)}" + (f" first={problems[0]}" if problems else ""))
    for o in overview:
        print(f"  {o.project_id}: progress={o.progress_percent}% remaining={o.remaining_mtoman} "
              f"contract={o.contract_value_mtoman if o.contract_value_mtoman is not None else '-'} owner={o.owner_node} "
              f"status={o.status} health={o.health} issues={o.issues} open={o.open_issues} "
              f"blocked_sub={o.blocked_subissues} records=" + ",".join(f"{k}:{v}" for k, v in o.records.items() if v))
    if evidence is not None:
        n_p, n_r = len(registry.projects), len(registry.records)  # type: ignore[union-attr]
        print(f"evidence: projects fa={evidence.grounded('projects', 'fa')}/{n_p} en={evidence.grounded('projects', 'en')}/{n_p} "
              f"records fa={evidence.grounded('records', 'fa')}/{n_r} en={evidence.grounded('records', 'en')}/{n_r}"
              + "".join(f" missing={f.ref}/{f.language}:{','.join(f.missing[:3])}" for f in evidence.failures()[:3]))
    print(f"gaps: total={len(report.gaps)} by_rule=" + ",".join(f"{k}:{v}" for k, v in report.by_rule().items())
          + " by_severity=" + ",".join(f"{k}:{v}" for k, v in report.by_severity().items()))
    for g in report.gaps:
        print(f"  {g.gap_id} {g.severity.value}" + (f" issue={g.issue_id}" if g.issue_id else "")
              + (f" {g.detail}" if g.detail else ""))
    if result is not None:
        rk = result.ranking
        print(f"priorities: ranked={len(rk.ranked)} excluded={len(rk.excluded)} ("
              + ",".join(f"{i}:{why}" for i, why in rk.excluded) + f") key={','.join(rk.key_ids) or '-'} "
              f"(top {pr.key_count}, score >= {pr.key_min_score:g})")
        for s in rk.ranked:
            print(f"  {s.rank}. {s.issue_id} score={s.score:g}{' KEY' if s.key else ''} top={explain(s, 'en')}")
        sv = result.sensitivity
        print(f"sensitivity: perturbations={sv.perturbations} top1_stable={sv.top1_stable}/{sv.perturbations} "
              f"key_set_stable={sv.key_set_stable}/{sv.perturbations}")
        print(f"legacy: phase7_order={','.join(result.legacy)} same_top1={result.same_top1} "
              f"top3_overlap={result.top_overlap(3)}/3")
        for issue_id, acts in result.next_actions.items():
            a = acts[0]
            print(f"next_action: {issue_id} -> {a.item_id} unblocks={len(a.unblocks)} ({','.join(a.unblocks)})")
    for lang, b in briefs.items():
        r = brief_results[lang]
        print(f"brief {lang}: key={len(b.items)} gaps={len(b.gaps)} words={b.words} chars={len(b.text)} "
              f"rule={r.total} {'accepted' if r.accepted else 'rejected'}"  # type: ignore[attr-defined]
              + (f" notes={';'.join(r.notes[:4])}" if not r.accepted else ""))  # type: ignore[attr-defined]
    kinds: dict[str, list[int]] = {}
    for r in neg_brief:
        bucket = kinds.setdefault(r.origin.split(":", 1)[1], [0, 0])
        bucket[0] += int(not r.accepted)
        bucket[1] += 1
    print(f"negative_controls: registry rejected={neg_registry_rejected}/{len(neg_registry)} "
          f"brief rejected={neg_brief_rejected}/{len(neg_brief)} by_kind="
          + ",".join(f"{k}:{v[0]}/{v[1]}" for k, v in kinds.items())
          + "".join(f" ACCEPTED={r['kind']}" for r in neg_registry if not r["rejected"]))
    if "error" in csv_info:
        print(f"csv: FAIL {csv_info['error']}")
    else:
        print(f"csv: files={csv_info.get('files', 0)} dir={csv_info.get('dir', '-')} "
              f"round_trip_problems={len(csv_info.get('problems', []) or [])}")  # type: ignore[arg-type]
    print(f"live: {live['status']}" + (f" ({live.get('reason')})" if live.get("reason") else ""))
    if live["status"] == "ok":
        print_live(live)
    print("checks: " + " ".join(f"{k2}={'ok' if v else 'FAIL'}" for k2, v in checks.items()))
    print(f"results_json: {out_json}")
    print(SEPARATOR_END)
    return 0 if status == "PASS" else 1


def live_step(pset: ProjectSettings, jset: JudgeSettings, client: OllamaClient, rubric, root: Path,  # noqa: ANN001
              rule_judge: RuleBasedJudge, validator: CitedFactValidator, briefs: dict[str, KeyIssueBrief]) -> dict:
    m = pset.model
    chat = OllamaChatModel(client, m.model, dict(m.options), m.think, m.keep_alive, m.timeout_s,
                           response_format=m.format or None)
    rule = BriefJudge(rule_judge)
    llm = None
    if pset.live.llm_judge:
        jm = jset.model
        judge_chat = OllamaChatModel(client, jm.model, dict(jm.options), jm.think, jm.keep_alive, jm.timeout_s,
                                     response_format=jm.format or None)
        prompts = load_judge_prompts(root / jset.files.prompt_dir)
        llm = BriefJudge(LlmJudge(rubric, prompts, judge_chat, name=f"llm:{jm.model}", retries=jset.run.retries,
                                  sources_char_budget=jset.run.sources_char_budget))
    t0 = time.perf_counter()
    items: list[AiBrief] = []
    templates: list[dict] = []
    for lang in pset.live.languages:
        brief = briefs.get(lang)
        if brief is None:
            continue
        system, user = advice_prompt(brief)
        t1 = time.perf_counter()
        ai = AiBrief(language=lang, status="error")
        try:
            res = chat.generate(system, user)
            ai.raw = res.text or ""
            ai.prompt_tokens, ai.completion_tokens = res.prompt_tokens, res.completion_tokens
            ai.parsed = parse_advice(ai.raw)
        except AdviceParseError as exc:
            ai.error = str(exc)
        except OllamaError as exc:
            ai.error = f"{type(exc).__name__}: {exc}"
        ai.seconds = time.perf_counter() - t1
        if ai.parsed is not None:
            ai.check = check_advice(ai.parsed, brief, validator)
            judged = [rule.judge_brief(brief, ai.parsed.brief, origin="priority-ai", suffix="ai")]
            if llm is not None:
                judged.append(llm.judge_brief(brief, ai.parsed.brief, origin="priority-ai", suffix="ai"))
            ai.verdicts = [verdict_dict(v) for v in judged]
            ai.status = "accepted" if ai.check.ok and all(v.accepted for v in judged) else "rejected"
        items.append(ai)
        print(f"  [{len(items)}] brief {lang}: {ai.status}", flush=True)
        if llm is not None:
            v = llm.judge_brief(brief)
            templates.append({"language": lang, "total": v.total, "accepted": v.accepted})
    seconds = time.perf_counter() - t0

    def verdict(ai: AiBrief, prefix: str) -> dict | None:
        return next((v for v in ai.verdicts if str(v["judge"]).startswith(prefix)), None)

    rows = []
    for ai in items:
        rv, lv = verdict(ai, "rule"), verdict(ai, "llm")
        rows.append({"language": ai.language, "status": ai.status, "error": ai.error,
                     "order": list(ai.parsed.order) if ai.parsed else [],
                     "grounded": bool(ai.check and ai.check.grounded),
                     "unsupported": list(ai.check.unsupported) if ai.check else [],
                     "invented_ids": list(ai.check.invented_ids) if ai.check else [],
                     "same_top": bool(ai.check and ai.check.same_top),
                     "mentioned": ai.check.mentioned if ai.check else 0,
                     "rule_total": rv["total"] if rv else None, "rule_accepted": bool(rv and rv["accepted"]),
                     "llm_total": lv["total"] if lv else None, "llm_accepted": bool(lv and lv["accepted"])})
    gen_times = [ai.seconds for ai in items if ai.raw]
    judge_times = [r.seconds for r in (llm.results if llm else [])]
    n = len(items)
    return {
        "model": m.model,
        "llm_judge": bool(llm),
        "generated": n,
        "parse_errors": sum(1 for ai in items if ai.parsed is None),
        "grounded": sum(1 for r in rows if r["grounded"]),
        "invented_ids": sum(len(r["invented_ids"]) for r in rows),
        "same_top": sum(1 for r in rows if r["same_top"]),
        "rule_accepted": sum(1 for r in rows if r["rule_accepted"]),
        "llm_accepted": sum(1 for r in rows if r["llm_accepted"]),
        "accepted": sum(1 for ai in items if ai.status == "accepted"),
        "templates": templates,
        "templates_llm_accepted": sum(1 for t in templates if t["accepted"]),
        "rows": rows,
        "briefs": [ai.to_dict() for ai in items],
        "timings": {"brief_avg_s": mean(gen_times), "judge_avg_s": mean(judge_times), "total_s": round(seconds, 1)},
        "tokens": {"prompt_avg": round(sum(ai.prompt_tokens for ai in items) / n) if n else None,
                   "completion_avg": round(sum(ai.completion_tokens for ai in items) / n) if n else None},
    }


def print_live(live: dict) -> None:
    n = live["generated"]
    print(f"live_brief: model={live['model']} think=off format=json generated={n} "
          f"parse_errors={live['parse_errors']} grounded={live['grounded']}/{n} invented_ids={live['invented_ids']} "
          f"same_top={live['same_top']}/{n} accepted={live['accepted']}/{n}")
    if live["llm_judge"]:
        t = len(live["templates"])
        print(f"live_judge: ai rule={live['rule_accepted']}/{n} llm={live['llm_accepted']}/{n} "
              f"combined={live['accepted']}/{n} templates llm={live['templates_llm_accepted']}/{t}")
    else:
        print(f"live_judge: rule only, ai accepted={live['rule_accepted']}/{n}")
    for r in live["rows"]:
        print(f"  brief {r['language']}: {r['status']} order={','.join(r['order']) or '-'} "
              f"mentioned={r['mentioned']} rule={r['rule_total']} llm={r['llm_total']}"
              + (f" unsupported={','.join(r['unsupported'][:3])}" if r["unsupported"] else "")
              + (f" invented={','.join(r['invented_ids'])}" if r["invented_ids"] else "")
              + (f" error={r['error'][:80]}" if r["error"] else ""))
    t = live["timings"]
    tok = live["tokens"]
    print(f"live_timings: brief_avg_s={t['brief_avg_s']} judge_avg_s={t['judge_avg_s']} "
          f"tokens_avg={tok['prompt_avg']}+{tok['completion_avg']} total_s={t['total_s']}")


if __name__ == "__main__":
    raise SystemExit(main())
