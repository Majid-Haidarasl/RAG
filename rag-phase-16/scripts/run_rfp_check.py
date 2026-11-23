#!/usr/bin/env python3
"""Phase 13: RFP generation from key issues and knowledge + proposal management.

Always (no Ollama needed):
* Rebuilds the Phase 12 inputs offline: registry, corpus, issues, executors,
  IKE graph of AR-ISS-024, project registry, research gaps and the weighted
  key-issue ranking of cycle 1403-Q2.
* Loads the RFP blueprints (data/rfp/rfp-blueprints.json), validates them
  (nodes, issues, sub-issue, documents, executors, weights sum to 1, mandatory
  sections) and grounds every requirement, knowledge link and weight in the
  corpus, in Persian and English.
* Selects the key issues that need an outside supplier and writes one RFP per
  blueprint from templates (Persian + English); judges it with the Phase 10
  rule judge (18/20).
* Loads the proposal registry (data/proposals/proposal-registry.json),
  validates and grounds it, scores every proposal with the transparent
  weighted formula, checks the recorded scores and the decision, writes the
  automated feedback per proposal (judged too) and links the outcome back to
  node knowledge.
* Broken copies (negative controls) of the blueprint, the registry, the RFP
  text and the feedback must all be rejected. Exports CSVs and reads them back.

Live (only if local Ollama answers and qwen3:8b is installed):
* AI summary of the RFP and AI feedback for the proposal that lost, in
  Persian and English (qwen3:8b, think off, JSON), fact-checked and judged by
  qwen3:8b and the rule judge together. Advice only. Without Ollama: SKIPPED.

The status depends on pytest, the earlier steps and the offline checks only.
Prints the ``PHASE 13 SUMMARY`` block and writes
``results/phase-13/rfp-check-<UTC>.json``.
"""

from __future__ import annotations

import argparse
import copy
from dataclasses import replace
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
_scripts = Path(__file__).resolve().parent
if str(_scripts) not in sys.path:
    sys.path.insert(0, str(_scripts))

from run_project_check import ike_digest, mean, parse_prior, probe_ollama, rel  # noqa: E402

from rag_core import __version__  # noqa: E402
from rag_core.hierarchy.application.workflows import load_and_validate  # noqa: E402
from rag_core.issues.application.services import load_issue_registry  # noqa: E402
from rag_core.issues.infrastructure.hierarchy_acl import HierarchyOrgDirectory  # noqa: E402
from rag_core.judging.application.services import LlmJudge, judge_all  # noqa: E402
from rag_core.judging.domain.rule_judge import RuleBasedJudge  # noqa: E402
from rag_core.judging.infrastructure.config import JudgeSettings, load_judge_settings  # noqa: E402
from rag_core.judging.infrastructure.prompt_yaml import load_judge_prompts, load_rubric  # noqa: E402
from rag_core.prioritization.application.services import PrioritizationService  # noqa: E402
from rag_core.prioritization.domain.scoring import PriorityScorer  # noqa: E402
from rag_core.prioritization.infrastructure.judging_acl import verdict_dict  # noqa: E402
from rag_core.prioritization.infrastructure.signals_acl import exposure_by_issue, issue_signals, sub_tasks  # noqa: E402
from rag_core.projects.infrastructure.config import ProjectSettings, load_project_settings  # noqa: E402
from rag_core.projects.infrastructure.corpus_acl import document_texts  # noqa: E402
from rag_core.projects.infrastructure.registry_json import read_registry_dict as read_project_dict  # noqa: E402
from rag_core.projects.infrastructure.registry_json import registry_from_dict as project_registry_from_dict  # noqa: E402
from rag_core.proposals.application.services import ProposalService  # noqa: E402
from rag_core.proposals.infrastructure.csv_export import export_tables, round_trip_problems  # noqa: E402
from rag_core.proposals.infrastructure.registry_json import read_registry_dict, registry_from_dict  # noqa: E402
from rag_core.qa.domain.fact_check import CitedFactValidator, source_numbers  # noqa: E402
from rag_core.rag.application.corpus import build_corpus_records  # noqa: E402
from rag_core.rag.infrastructure.config import RagSettings, load_settings  # noqa: E402
from rag_core.rag.infrastructure.ollama import OllamaChatModel, OllamaClient, OllamaError  # noqa: E402
from rag_core.research_gaps.application.services import GapReport, GapService  # noqa: E402
from rag_core.research_gaps.domain.rules import GapRuleBook  # noqa: E402
from rag_core.research_gaps.infrastructure.inputs_acl import build_inputs, ike_items  # noqa: E402
from rag_core.rfp.application.services import RfpRun, RfpService  # noqa: E402
from rag_core.rfp.domain.advice import AiReply, ReplyParseError, check_reply, parse_reply  # noqa: E402
from rag_core.rfp.domain.evidence import ground_blueprint  # noqa: E402
from rag_core.rfp.domain.validation import BlueprintValidator  # noqa: E402
from rag_core.rfp.infrastructure.blueprint_json import blueprints_from_dict, read_blueprint_dict  # noqa: E402
from rag_core.rfp.infrastructure.config import RfpSettings, load_rfp_settings  # noqa: E402
from rag_core.rfp.infrastructure.inputs_acl import executor_nodes, gap_views, item_views, key_issue_views  # noqa: E402
from rag_core.rfp.infrastructure.judging_acl import feedback_task, negative_cases, rfp_task, summary_case  # noqa: E402
from rag_core.rfp.infrastructure.prompts_yaml import RfpPrompts, load_rfp_prompts  # noqa: E402
from rag_core.shared_kernel.errors import DomainError  # noqa: E402
from rag_core.transfer.infrastructure.sources_acl import document_versions  # noqa: E402

KIT = f"rag-core {__version__} (phase 13 rfp generation, proposal management)"
SEPARATOR_START = "======== PHASE 13 SUMMARY ========"
SEPARATOR_END = "======== END PHASE 13 SUMMARY ========"
LOAD_ERRORS = (DomainError, ValueError, KeyError, TypeError, ArithmeticError)


def find_root(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.resolve()
    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents, ROOT_CANDIDATE]:
        if (candidate / "pyproject.toml").is_file() and (candidate / "config" / "rfp.yaml").is_file():
            return candidate
    raise SystemExit("could not find the repo root (pyproject.toml + config/rfp.yaml)")


# ---- negative controls ---------------------------------------------------------------
def _find(items: list[dict], item_id: str) -> dict:
    return next(i for i in items if i["id"] == item_id)


def _mutations(raw: dict, changes: list[tuple[str, str, object]]) -> list[tuple[str, str, dict]]:
    out: list[tuple[str, str, dict]] = []
    for kind, expected, change in changes:
        data = copy.deepcopy(raw)
        try:
            change(data)  # type: ignore[operator]
        except (KeyError, StopIteration, IndexError, ValueError):
            continue
        out.append((kind, expected, data))
    return out


def blueprint_mutations(raw: dict) -> list[tuple[str, str, dict]]:
    """Broken copies of the shipped blueprint file: (kind, expected problem code, data)."""
    def bp(d: dict) -> dict:
        return d["blueprints"][0]

    def drop_acceptance(d: dict) -> None:
        reqs = bp(d)["requirements"]
        reqs.remove(_find(reqs, "REQ-ACCEPTANCE"))

    def invent_number(d: dict) -> None:
        r = _find(bp(d)["requirements"], "REQ-EVALUATION")
        if "60%" not in r["statement_en"]:
            raise ValueError("60% not in the statement")
        r["statement_en"] = r["statement_en"].replace("60%", "65%")

    return _mutations(raw, [
        ("fabricated_document", "unknown_document",
         lambda d: _find(bp(d)["requirements"], "REQ-SCOPE")["evidence"].append("AR-XYZ-999")),
        ("weights_not_one", "weights_not_one", lambda d: _find(bp(d)["criteria"], "CRT-FIN").__setitem__("weight", "0.5")),
        ("invented_number", "ungrounded", invent_number),
        ("missing_mandatory_section", "missing_section", drop_acceptance),
        ("unknown_node", "unknown_node", lambda d: bp(d).__setitem__("owner_node", "N-XXX")),
        ("executor_wrong_node", "executor_node_mismatch",
         lambda d: _find(bp(d)["links"], "LNK-DESIGN").__setitem__("executor", "EX-REZA-ABBASI")),
        ("unknown_issue", "unknown_issue", lambda d: bp(d)["issues"].append("AR-ISS-099")),
    ])


def proposal_mutations(raw: dict) -> list[tuple[str, str, dict]]:
    """Broken copies of the shipped proposal registry: (kind, expected problem code, data)."""
    def prp(d: dict, pid: str) -> dict:
        return _find(d["proposals"], pid)

    def drop_section(d: dict) -> None:
        prp(d, "PRP-B")["sections"].remove("test_plan")

    return _mutations(raw, [
        # 240 / 285 x 100 = 84.2: a price formula instead of the recorded financial score
        ("price_formula", "published_mismatch", lambda d: prp(d, "PRP-A")["scores"].__setitem__("CRT-FIN", "84.2")),
        ("wrong_price", "ungrounded_number", lambda d: prp(d, "PRP-B").__setitem__("price_mtoman", 250)),
        ("fabricated_subscore", "unknown_criterion", lambda d: prp(d, "PRP-A")["scores"].__setitem__("CRT-API", "90")),
        ("missing_score", "missing_score", lambda d: prp(d, "PRP-A")["scores"].pop("CRT-FIN")),
        ("score_out_of_range", "score_range", lambda d: prp(d, "PRP-B")["scores"].__setitem__("CRT-TECH", "110")),
        ("missing_section", "missing_section", drop_section),
        ("decision_mismatch", "decision_mismatch", lambda d: d["decision"].__setitem__("selected", "PRP-B")),
        ("unknown_rfp", "unknown_rfp", lambda d: d.__setitem__("rfp_id", "AR-RFP-1403-99")),
        ("duplicate_id", "duplicate_id", lambda d: d["proposals"].append(copy.deepcopy(d["proposals"][0]))),
        ("invented_feedback_number", "ungrounded_statement",
         lambda d: prp(d, "PRP-B").__setitem__("feedback_en", prp(d, "PRP-B")["feedback_en"] + " Its score was 91.")),
    ])


def blueprint_rejects(data: dict, validator: BlueprintValidator, texts, fact_validator) -> list[str]:  # noqa: ANN001
    try:
        bps = blueprints_from_dict(data)
    except LOAD_ERRORS as exc:
        return [f"load:{type(exc).__name__}"]
    codes = [p.code for p in validator.validate(bps)]
    for bp in bps:
        if not ground_blueprint(bp, texts, fact_validator, source_numbers).ok:
            codes.append("ungrounded")
    return codes


def proposal_rejects(data: dict, service: ProposalService) -> list[str]:
    try:
        registry = registry_from_dict(data)
    except LOAD_ERRORS as exc:
        return [f"load:{type(exc).__name__}"]
    return service.audit(registry).codes


def control_row(kind: str, expected: str, codes: list[str]) -> dict:
    return {"kind": kind, "expected": expected, "rejected": bool(codes), "expected_seen": expected in codes,
            "codes": codes[:6]}


def main() -> int:  # noqa: C901 - one linear check script, like the earlier phases
    parser = argparse.ArgumentParser(description="Phase 13 RFP generation and proposal management.")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--config", type=Path, default=None, help="config/rag.yaml (Ollama endpoint)")
    parser.add_argument("--judge-config", type=Path, default=None, help="config/judge.yaml")
    parser.add_argument("--project-config", type=Path, default=None, help="config/projects.yaml")
    parser.add_argument("--rfp-config", type=Path, default=None, help="config/rfp.yaml")
    parser.add_argument("--out", type=Path, default=None, help="folder for rfp-check-*.json")
    parser.add_argument("--exports", type=Path, default=None, help="CSV folder (default from config/rfp.yaml)")
    parser.add_argument("--no-live", action="store_true", help="skip the Ollama step")
    for name in ("passed", "failed", "errors", "skipped", "exit", "line"):
        parser.add_argument(f"--pytest-{name}", default=None)
    parser.add_argument("--python-version", default=None)
    parser.add_argument("--prior", default="", help="earlier steps as name=exit,...")
    args = parser.parse_args()

    root = find_root(args.root)
    settings: RagSettings = load_settings(args.config or root / "config" / "rag.yaml")
    jset: JudgeSettings = load_judge_settings(args.judge_config or root / "config" / "judge.yaml")
    pset: ProjectSettings = load_project_settings(args.project_config or root / "config" / "projects.yaml")
    rset: RfpSettings = load_rfp_settings(args.rfp_config or root / "config" / "rfp.yaml")
    out_dir = args.out or root / "results" / "phase-13"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_json = out_dir / f"rfp-check-{stamp}.json"
    csv_dir = args.exports or root / rset.storage.csv_dir
    cycle_id = rset.cycle.id
    langs = rset.live.languages
    t0 = time.perf_counter()
    errors: list[str] = []

    # ---- Phase 12 inputs (offline)
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
        issues = list(load_issue_registry(root / "data" / "issues", HierarchyOrgDirectory(org)).issues)
        if not issues:
            errors.append("issues: the issue registry did not load")
        else:
            try:
                ike, executors = ike_digest(root, settings, corpus, org, issues, pset.case)
            except Exception as exc:  # noqa: BLE001 - reported as a failed check
                errors.append(f"ike: {type(exc).__name__}: {exc}")
    project_registry = None
    try:
        project_registry = project_registry_from_dict(read_project_dict(root / pset.storage.registry_dir))
    except Exception as exc:  # noqa: BLE001
        errors.append(f"projects: {type(exc).__name__}: {exc}")
    report = GapReport()
    ranking = None
    if project_registry is not None and issues:
        report = GapService(GapRuleBook(pset.gap_rules)).detect(build_inputs(project_registry, issues, ike_items(ike)))
        pr = pset.prioritization
        signals = issue_signals(issues, report.count_by_issue(), exposure_by_issue(project_registry.projects))
        scorer = PriorityScorer(pr.weights, pr.caps, key_count=pr.key_count, key_min_score=pr.key_min_score)
        ranking = PrioritizationService(scorer, pr.sensitivity_ratios).run(signals, sub_tasks(issues)).ranking

    nodes = {str(n.identifier) for n in org.all_nodes()} if org is not None else set()
    item_map = item_views(issues)
    issue_ids = {str(i.identifier) for i in issues} | set(item_map)
    ex_nodes = executor_nodes(executors)
    fact_validator = CitedFactValidator()

    # ---- blueprints and prompts
    raw_bp: dict = {}
    blueprints: list = []
    try:
        raw_bp = read_blueprint_dict(root / rset.storage.blueprint_dir)
        blueprints = blueprints_from_dict(raw_bp)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"blueprints: {type(exc).__name__}: {exc}")
    prompts = RfpPrompts()
    try:
        prompts = load_rfp_prompts(root / rset.storage.prompt_dir)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"prompts: {type(exc).__name__}: {exc}")
    bp_validator = BlueprintValidator(nodes, set(versions), issue_ids, ex_nodes)
    bp_problems = bp_validator.validate(blueprints)
    bp_evidence = {b.blueprint_id: ground_blueprint(b, texts, fact_validator, source_numbers, langs)
                   for b in blueprints}

    # ---- RFP generation + rule judge (an RFP is a document: larger character limit)
    rubric = load_rubric(root / jset.files.rubric)
    rule_judge = RuleBasedJudge(rubric, fact_validator, jset.rules)
    rfp_judge = RuleBasedJudge(rubric, fact_validator, replace(jset.rules, max_summary_chars=rset.judging.max_rfp_chars))
    key = key_issue_views(ranking.ranked, issues) if ranking is not None else []
    run = RfpRun()
    if key and blueprints:
        run = RfpService(blueprints, rset.candidates.categories, rset.candidates.targets,
                         prompts.headings).run(key, gap_views(report.gaps), item_map, cycle_id, langs)
    rfp_cases = {(rid, lang): summary_case(f"P13-rfp-{rid}-{lang}", lang, rfp_task(rid, lang), d.text, d.facts,
                                           d.items, d.gaps)
                 for rid, by_lang in run.drafts.items() for lang, d in by_lang.items()}
    rfp_results = dict(zip(rfp_cases, judge_all(rfp_judge, list(rfp_cases.values()))))

    # ---- proposals: audit, evaluation, feedback, knowledge
    raw_prp: dict = {}
    registry = None
    try:
        raw_prp = read_registry_dict(root / rset.storage.proposal_dir)
        registry = registry_from_dict(raw_prp)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"proposals: {type(exc).__name__}: {exc}")
    service = ProposalService(blueprints, set(versions), texts, fact_validator, source_numbers, langs)
    audit = service.audit(registry) if registry is not None else None
    evaluation = audit.evaluation if audit is not None else None
    feedback = service.feedback(registry, evaluation) if registry is not None and evaluation is not None else {}
    fb_cases = {(pid, lang): summary_case(f"P13-feedback-{pid}-{lang}", lang, feedback_task(pid, lang), f.text,
                                          f.facts, f.items, f.gaps, origin="feedback-template")
                for pid, by_lang in feedback.items() for lang, f in by_lang.items()}
    fb_results = dict(zip(fb_cases, judge_all(rule_judge, list(fb_cases.values()))))
    knowledge = service.knowledge(registry, evaluation, nodes, ex_nodes) \
        if registry is not None and evaluation is not None else None

    # ---- negative controls
    neg_bp = [control_row(k, e, blueprint_rejects(d, bp_validator, texts, fact_validator))
              for k, e, d in blueprint_mutations(raw_bp)] if raw_bp else []
    neg_prp = [control_row(k, e, proposal_rejects(d, service)) for k, e, d in proposal_mutations(raw_prp)] \
        if raw_prp else []
    neg_text = judge_all(rfp_judge, [c for (rid, _lang), base in rfp_cases.items()
                                     for c in negative_cases(base, run.drafts[rid][_lang].items)])
    neg_fb = judge_all(rule_judge, [c for (pid, _lang), base in fb_cases.items()
                                    for c in negative_cases(base, feedback[pid][_lang].items)])

    # ---- CSV export
    csv_info: dict[str, object] = {}
    bp_by_rfp = {b.rfp_id: b for b in blueprints}
    csv_bp = bp_by_rfp.get(registry.rfp_id) if registry is not None else None
    if csv_bp is not None and registry is not None and evaluation is not None:
        tables = {
            "rfp_requirements": [{"requirement_id": r.requirement_id, "rfp_id": csv_bp.rfp_id, "section": r.section.value,
                                  "mandatory": r.mandatory, "answered_in": r.answered_in,
                                  "statement_en": r.statement_en, "statement_fa": r.statement_fa,
                                  "evidence": list(r.evidence)} for r in csv_bp.requirements],
            "proposals": [{"proposal_id": p.proposal_id, "rfp_id": registry.rfp_id, "vendor_en": p.vendor_en,
                           "vendor_fa": p.vendor_fa, "price_mtoman": p.price_mtoman, "duration_weeks": p.duration_weeks,
                           "technology": p.technology, "version": p.version, "sections": list(p.sections),
                           "evidence": list(p.evidence)} for p in registry.proposals],
            "evaluation": [{"row_id": f"{s.proposal_id}/{x.criterion_id}", "proposal_id": s.proposal_id,
                            "criterion_id": x.criterion_id, "weight": x.weight, "score": x.score,
                            "contribution": x.contribution, "weighted": s.weighted, "published": s.published,
                            "rank": s.rank, "compliant": s.compliant} for s in evaluation.scores for x in s.lines],
            "feedback": [{"row_id": f"{pid}/{lang}", "proposal_id": pid, "language": lang, "chars": f.chars,
                          "text": f.text} for pid, by_lang in feedback.items() for lang, f in by_lang.items()],
            "knowledge_links": [{"link_id": r.link_id, "rfp_id": r.rfp_id, "node": r.node, "executor": r.executor,
                                 "requirements": list(r.requirements), "evidence": list(r.evidence),
                                 "valid": r.valid} for r in (knowledge.links if knowledge else [])],
        }
        try:
            files = export_tables(tables, csv_dir, registry.rfp_id)
            csv_info = {"dir": rel(root, files[0].parent), "files": len(files),
                        "problems": round_trip_problems(tables, csv_dir, registry.rfp_id)}
        except Exception as exc:  # noqa: BLE001
            errors.append(f"csv: {type(exc).__name__}: {exc}")
            csv_info = {"error": f"{type(exc).__name__}: {exc}"}

    # ---- live step
    live: dict[str, object] = {"status": "skipped", "reason": "disabled with --no-live"}
    ollama_info: dict[str, object] = {"base_url": settings.ollama.base_url}
    if not args.no_live:
        if not run.drafts or not feedback or prompts.rfp_summary is None or prompts.feedback is None:
            live = {"status": "skipped", "reason": "no RFP, feedback or prompts to work on"}
        else:
            client, reason, ollama_info = probe_ollama(settings, rset.model.model)
            if client is None:
                live = {"status": "skipped", "reason": reason}
            else:
                print("live step: Ollama", ollama_info.get("version"), "-> qwen3:8b RFP summary, feedback and judge",
                      flush=True)
                try:
                    loser = evaluation.runner_up.proposal_id if evaluation and evaluation.runner_up else ""
                    live = {"status": "ok", **live_step(rset, jset, client, rubric, root, rule_judge, fact_validator,
                                                        prompts, run, feedback, loser)}
                except Exception as exc:  # noqa: BLE001 - the live step never breaks the kit status
                    live = {"status": "fail", "reason": f"{type(exc).__name__}: {exc}",
                            "traceback": traceback.format_exc(limit=5)}
    total_s = time.perf_counter() - t0

    # ---- checks
    prior = parse_prior(args.prior)
    all_drafts = run.all_drafts()
    bp_ev_ok = bool(bp_evidence) and all(e.ok for e in bp_evidence.values())
    neg_text_rejected = sum(1 for r in neg_text if not r.accepted)
    neg_fb_rejected = sum(1 for r in neg_fb if not r.accepted)
    validator_codes = {"published_mismatch", "decision_mismatch", "no_winner", "ungrounded_number",
                       "ungrounded_statement"}
    checks = {
        "pytest": args.pytest_exit in (None, "0", 0),
        "prior_steps": all(v == "0" for v in prior.values()),
        "inputs_loaded": org is not None and bool(issues) and ike is not None and ranking is not None
        and bool(blueprints) and registry is not None
        and not any(e.startswith(("registry", "issues", "ike", "projects", "blueprints", "prompts", "proposals"))
                    for e in errors),
        "blueprint_valid": bool(blueprints) and not bp_problems,
        "evidence_grounded": bp_ev_ok and audit is not None and audit.evidence is not None and audit.evidence.ok,
        "rfp_generated": bool(run.sourcing) and bool(run.drafts) and len(all_drafts) == len(run.drafts) * len(langs)
        and all(bool(d.requirement_ids) and all(f"[{rid}]" in d.text for rid in d.requirement_ids)
                for d in all_drafts),
        "rfp_accepted": bool(rfp_results) and all(r.accepted for r in rfp_results.values()),
        "proposals_valid": audit is not None and not [p for p in audit.problems if p.code not in validator_codes],
        "evaluation_matches_published": evaluation is not None and evaluation.published_total > 0
        and evaluation.published_match == evaluation.published_total,
        "decision_consistent": evaluation is not None and evaluation.decision_consistent,
        "feedback_accepted": bool(fb_results) and all(r.accepted for r in fb_results.values()),
        "knowledge_linked": knowledge is not None and knowledge.ok,
        "negative_controls_rejected": bool(neg_bp) and bool(neg_prp) and bool(neg_text) and bool(neg_fb)
        and all(r["rejected"] and r["expected_seen"] for r in [*neg_bp, *neg_prp])
        and neg_text_rejected == len(neg_text) and neg_fb_rejected == len(neg_fb),
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
        "pytest": {"passed": args.pytest_passed, "failed": args.pytest_failed, "errors": args.pytest_errors,
                   "skipped": args.pytest_skipped, "exit": args.pytest_exit, "result_line": args.pytest_line},
        "prior_steps": prior,
        "cycle": {"id": cycle_id, "cutoff": rset.cycle.cutoff},
        "key_issues": [k.__dict__ for k in key],
        "blueprints": {"count": len(blueprints), "problems": [p.__dict__ for p in bp_problems],
                       "evidence": {k: v.to_dict() for k, v in bp_evidence.items()}},
        "rfp": run.to_dict(),
        "rfp_judge": {f"{rid}/{lang}": verdict_dict(r) for (rid, lang), r in rfp_results.items()},
        "proposals": audit.to_dict() if audit is not None else None,
        "feedback": {pid: {lang: f.to_dict() for lang, f in by_lang.items()} for pid, by_lang in feedback.items()},
        "feedback_judge": {f"{pid}/{lang}": verdict_dict(r) for (pid, lang), r in fb_results.items()},
        "knowledge": knowledge.to_dict() if knowledge is not None else None,
        "negative_controls": {"blueprint": neg_bp, "proposals": neg_prp,
                              "rfp_text": [{"case_id": r.case_id, "origin": r.origin, "accepted": r.accepted,
                                            "total": r.total} for r in neg_text],
                              "feedback": [{"case_id": r.case_id, "origin": r.origin, "accepted": r.accepted,
                                            "total": r.total} for r in neg_fb]},
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
    for name in ("exit", "passed", "failed", "errors", "skipped"):
        print(f"pytest_{name}: {getattr(args, f'pytest_{name}')}")
    print("prior_steps: " + (" ".join(f"{k}={v}" for k, v in prior.items()) or "none"))
    if errors:
        print("errors: " + " | ".join(errors))
    print(f"inputs: cycle={cycle_id} key={','.join(k.issue_id for k in key) or '-'} gaps={len(report.gaps)} "
          f"blueprints={len(blueprints)} proposals={len(registry.proposals) if registry else 0} "
          f"executors={len(executors)}")
    sourcing = run.sourcing
    others = [c for c in run.candidates if not c.has_rfp]
    print(f"rfp_candidates: key={len(run.candidates)} sourcing={len(sourcing)} ("
          + ",".join(f"{c.issue_id}:{c.reason}->{c.blueprint_id}" for c in sourcing) + f") none={len(others)} ("
          + ",".join(f"{c.issue_id}:{c.reason}" for c in others) + f") rfps={len(run.drafts)}")
    for b in blueprints:
        ev = bp_evidence[b.blueprint_id]
        weights = "+".join(str(c.percent) for c in b.criteria)
        print(f"blueprint: {b.blueprint_id} rfp={b.rfp_id} requirements={len(b.requirements)} "
              f"(mandatory={sum(1 for r in b.requirements if r.mandatory)}) criteria={len(b.criteria)} "
              f"weights={weights} links={len(b.links)} problems={len(bp_problems)}"
              + (f" first={bp_problems[0]}" if bp_problems else ""))
        print("evidence: blueprint " + " ".join(f"{lang}={ev.grounded(lang)}/{ev.total(lang)}" for lang in langs)
              + " weights " + " ".join(f"{lang}={sum(1 for w in ev.weights if w.language == lang and w.grounded)}/"
                                       f"{sum(1 for w in ev.weights if w.language == lang)}" for lang in langs)
              + "".join(f" missing={f.ref}/{f.language}:{','.join(f.missing[:3])}" for f in ev.failures()[:3]))
    if audit is not None and audit.evidence is not None:
        pe = audit.evidence
        print("evidence: proposals numbers " + " ".join(f"{lang}={pe.grounded('numbers', lang)}/"
                                                       f"{pe.total('numbers', lang)}" for lang in langs)
              + " statements " + " ".join(f"{lang}={pe.grounded('statements', lang)}/"
                                         f"{pe.total('statements', lang)}" for lang in langs)
              + "".join(f" missing={f.ref}/{f.language}:{','.join(f.missing[:3])}" for f in pe.failures()[:3]))
    for (rid, lang), r in rfp_results.items():
        d = run.drafts[rid][lang]
        print(f"rfp {rid} {lang}: sections={len(d.sections)} requirements={len(d.requirement_ids)} "
              f"issues={','.join(d.issues)} gaps={len(d.gap_ids)} words={d.words} chars={d.chars} "
              f"rule={r.total} {'accepted' if r.accepted else 'rejected'}"
              + (f" notes={';'.join(r.notes[:4])}" if not r.accepted else ""))
    if evaluation is not None:
        for s in evaluation.scores:
            parts = " + ".join(f"{x.criterion_id} {x.score}x{x.weight}={x.contribution}" for x in s.lines)
            print(f"evaluation: {s.proposal_id} weighted={s.weighted} ({parts}) published={s.published} "
                  f"match={'yes' if s.matches_published else 'NO'} rank={s.rank} compliant={'yes' if s.compliant else 'no'}"
                  f" price={s.price} weeks={s.duration}")
        w, c, f = evaluation.winner, evaluation.cheapest, evaluation.fastest
        print(f"decision: selected={evaluation.selected or '-'} winner={w.proposal_id if w else '-'} "
              f"consistent={'yes' if evaluation.decision_consistent else 'NO'} margin={evaluation.margin} "
              f"cheapest={c.proposal_id if c else '-'} price_gap={evaluation.price_gap} "
              f"fastest={f.proposal_id if f else '-'} duration_gap={evaluation.duration_gap} "
              f"published_match={evaluation.published_match}/{evaluation.published_total}")
    if audit is not None and audit.problems:
        print("proposal_problems: " + ",".join(str(p) for p in audit.problems[:6]))
    for (pid, lang), r in fb_results.items():
        fd = feedback[pid][lang]
        print(f"feedback {pid} {lang}: chars={fd.chars} rule={r.total} {'accepted' if r.accepted else 'rejected'}"
              + (f" notes={';'.join(r.notes[:4])}" if not r.accepted else ""))
    if knowledge is not None:
        o = knowledge.outcome
        print(f"knowledge: links={len(knowledge.links)} valid={knowledge.valid} nodes={len(knowledge.nodes)} "
              f"executors={len(knowledge.executors)} outcome={o.item if o else '-'}<-{o.selected if o else '-'}"
              + "".join(f" BAD={r.link_id}:{r.problem}" for r in knowledge.links if not r.valid))
    kinds: dict[str, list[int]] = {}
    for r in [*neg_text, *neg_fb]:
        bucket = kinds.setdefault(r.origin.split(":", 1)[1], [0, 0])
        bucket[0] += int(not r.accepted)
        bucket[1] += 1
    print(f"negative_controls: blueprint rejected={sum(1 for r in neg_bp if r['rejected'] and r['expected_seen'])}"
          f"/{len(neg_bp)} proposals rejected={sum(1 for r in neg_prp if r['rejected'] and r['expected_seen'])}"
          f"/{len(neg_prp)} rfp_text rejected={neg_text_rejected}/{len(neg_text)} "
          f"feedback rejected={neg_fb_rejected}/{len(neg_fb)} by_kind="
          + ",".join(f"{k}:{v[0]}/{v[1]}" for k, v in kinds.items())
          + "".join(f" MISSED={r['kind']}({','.join(r['codes'][:2]) or 'accepted'})"
                    for r in [*neg_bp, *neg_prp] if not (r["rejected"] and r["expected_seen"])))
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


def live_step(rset: RfpSettings, jset: JudgeSettings, client: OllamaClient, rubric, root: Path,  # noqa: ANN001
              rule_judge: RuleBasedJudge, validator: CitedFactValidator, prompts: RfpPrompts, run: RfpRun,
              feedback: dict, loser: str) -> dict:
    m = rset.model
    chat = OllamaChatModel(client, m.model, dict(m.options), m.think, m.keep_alive, m.timeout_s,
                           response_format=m.format or None)
    llm = None
    if rset.live.llm_judge:
        jm = jset.model
        judge_chat = OllamaChatModel(client, jm.model, dict(jm.options), jm.think, jm.keep_alive, jm.timeout_s,
                                     response_format=jm.format or None)
        llm = LlmJudge(rubric, load_judge_prompts(root / jset.files.prompt_dir), judge_chat, name=f"llm:{jm.model}",
                       retries=jset.run.retries, sources_char_budget=jset.run.sources_char_budget)
    jobs: list[tuple[str, str, str, tuple, tuple, tuple]] = []   # task, subject, lang, facts, items, gaps
    rid = next(iter(run.drafts))
    for lang in rset.live.languages:
        if "rfp_summary" in rset.live.tasks and lang in run.drafts[rid]:
            d = run.drafts[rid][lang]
            jobs.append(("rfp_summary", rid, lang, d.facts, d.items, d.items[1:]))
        if "feedback" in rset.live.tasks and loser and lang in feedback.get(loser, {}):
            f = feedback[loser][lang]
            jobs.append(("feedback", loser, lang, f.facts, f.items, f.gaps))
    t0 = time.perf_counter()
    items: list[AiReply] = []
    templates: list[dict] = []
    for task, subject, lang, facts, ids, gaps in jobs:
        prompt = prompts.rfp_summary if task == "rfp_summary" else prompts.feedback
        system, user = prompt.render(lang, facts="\n".join(facts), items=", ".join(dict.fromkeys([*ids, *gaps])))  # type: ignore[union-attr]
        ai = AiReply(task, subject, lang)
        t1 = time.perf_counter()
        try:
            res = chat.generate(system, user)
            ai.raw = res.text or ""
            ai.prompt_tokens, ai.completion_tokens = res.prompt_tokens, res.completion_tokens
            ai.parsed = parse_reply(ai.raw, "summary" if task == "rfp_summary" else "feedback")
        except ReplyParseError as exc:
            ai.error = str(exc)
        except OllamaError as exc:
            ai.error = f"{type(exc).__name__}: {exc}"
        ai.seconds = time.perf_counter() - t1
        if ai.parsed is not None:
            ai.check = check_reply(ai.parsed, facts, ids, validator)
            task_text = rfp_task(subject, lang) if task == "rfp_summary" else feedback_task(subject, lang)
            case = summary_case(f"P13-{task}-{subject}-{lang}-ai", lang, task_text, ai.parsed.text, facts, ids, gaps,
                                origin="rfp-ai")
            judged = judge_all(rule_judge, [case]) + (judge_all(llm, [case]) if llm is not None else [])
            ai.verdicts = [verdict_dict(v) for v in judged]
            ai.status = "accepted" if ai.check.ok and all(v.accepted for v in judged) else "rejected"
        items.append(ai)
        print(f"  [{len(items)}] {task} {subject} {lang}: {ai.status}", flush=True)
        if llm is not None and task == "feedback":
            f = feedback[subject][lang]
            base = summary_case(f"P13-feedback-{subject}-{lang}-llm", lang, feedback_task(subject, lang), f.text,
                                f.facts, f.items, f.gaps, origin="feedback-template")
            v = judge_all(llm, [base])[0]
            templates.append({"task": task, "subject": subject, "language": lang, "total": v.total,
                              "accepted": v.accepted})
    seconds = time.perf_counter() - t0

    def verdict(ai: AiReply, prefix: str) -> dict | None:
        return next((v for v in ai.verdicts if str(v["judge"]).startswith(prefix)), None)

    rows = []
    for ai in items:
        rv, lv = verdict(ai, "rule"), verdict(ai, "llm")
        rows.append({"task": ai.task, "subject": ai.subject, "language": ai.language, "status": ai.status,
                     "error": ai.error, "grounded": bool(ai.check and ai.check.grounded),
                     "unsupported": list(ai.check.unsupported) if ai.check else [],
                     "invented_ids": list(ai.check.invented_ids) if ai.check else [],
                     "mentioned": f"{ai.check.mentioned}/{ai.check.expected}" if ai.check else "0/0",
                     "rule_total": rv["total"] if rv else None, "rule_accepted": bool(rv and rv["accepted"]),
                     "llm_total": lv["total"] if lv else None, "llm_accepted": bool(lv and lv["accepted"])})
    n = len(items)
    return {
        "model": m.model,
        "llm_judge": bool(llm),
        "generated": n,
        "parse_errors": sum(1 for ai in items if ai.parsed is None),
        "grounded": sum(1 for r in rows if r["grounded"]),
        "invented_ids": sum(len(r["invented_ids"]) for r in rows),
        "rule_accepted": sum(1 for r in rows if r["rule_accepted"]),
        "llm_accepted": sum(1 for r in rows if r["llm_accepted"]),
        "accepted": sum(1 for ai in items if ai.status == "accepted"),
        "templates": templates,
        "templates_llm_accepted": sum(1 for t in templates if t["accepted"]),
        "rows": rows,
        "replies": [ai.to_dict() for ai in items],
        "timings": {"generate_avg_s": mean([ai.seconds for ai in items if ai.raw]), "total_s": round(seconds, 1)},
        "tokens": {"prompt_avg": round(sum(ai.prompt_tokens for ai in items) / n) if n else None,
                   "completion_avg": round(sum(ai.completion_tokens for ai in items) / n) if n else None},
    }


def print_live(live: dict) -> None:
    n = live["generated"]
    print(f"live_ai: model={live['model']} think=off format=json generated={n} parse_errors={live['parse_errors']} "
          f"grounded={live['grounded']}/{n} invented_ids={live['invented_ids']} accepted={live['accepted']}/{n}")
    if live["llm_judge"]:
        t = len(live["templates"])
        print(f"live_judge: ai rule={live['rule_accepted']}/{n} llm={live['llm_accepted']}/{n} "
              f"combined={live['accepted']}/{n} feedback_templates llm={live['templates_llm_accepted']}/{t}")
    else:
        print(f"live_judge: rule only, ai accepted={live['rule_accepted']}/{n}")
    for r in live["rows"]:
        print(f"  {r['task']} {r['subject']} {r['language']}: {r['status']} mentioned={r['mentioned']} "
              f"rule={r['rule_total']} llm={r['llm_total']}"
              + (f" unsupported={','.join(r['unsupported'][:3])}" if r["unsupported"] else "")
              + (f" invented={','.join(r['invented_ids'])}" if r["invented_ids"] else "")
              + (f" error={r['error'][:80]}" if r["error"] else ""))
    t, tok = live["timings"], live["tokens"]
    print(f"live_timings: generate_avg_s={t['generate_avg_s']} tokens_avg={tok['prompt_avg']}+{tok['completion_avg']} "
          f"total_s={t['total_s']}")


if __name__ == "__main__":
    raise SystemExit(main())
