#!/usr/bin/env python3
"""Phase 10: LLM-as-judge and quality control.

Always (no Ollama needed):
* Loads the judge rubric (``config/prompts/judge/rubric.yaml``: five criteria,
  20 points, accept at 18 with per-criterion minimums) and the judge prompts,
  and renders every prompt once.
* Runs the score parser on the reply fixtures (``data/judge/parser-cases.json``).
* Runs the deterministic rule judge on:
  - the calibration set (``data/judge/calibration-set.json``, gold labels);
  - the Phase 9 template summaries of AR-ISS-024 (Persian and English);
  - the Phase 8 live answers and Phase 9 live summaries from the newest
    ``results/phase-08/rag-demo-*.json`` / ``results/phase-09/ike-check-*.json``
    (only if those runs had a live step);
  - negative controls: deliberately broken copies of the good outputs.

Live (only if local Ollama answers and qwen3:8b is installed):
* qwen3:8b (think off, temperature 0, JSON format) judges the key outputs
  (Phase 8 answers, Phase 9 summaries), the calibration set and the negative
  controls; acceptance at 18/20, agreement with gold labels and with the
  rule judge, rejection of the negative controls, parse statistics and timings.
  Without Ollama the live step prints SKIPPED with the reason.

The overall status depends on pytest, the earlier steps and the offline
checks only; the live step is reported separately (live: ok/skipped/fail).
Prints the ``PHASE 10 SUMMARY`` block and writes
``results/phase-10/judge-check-<UTC>.json``.
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
from rag_core.executors.application.services import (
    ExecutorMatchingService,
    load_executor_registry,
)  # noqa: E402
from rag_core.executors.infrastructure.hierarchy_acl import HierarchyTeamDirectory  # noqa: E402
from rag_core.executors.infrastructure.issues_acl import referral_requests  # noqa: E402
from rag_core.ike.application.services import IkeService, IkeSummaryService  # noqa: E402
from rag_core.ike.infrastructure.executors_acl import executor_names, referrals_by_item  # noqa: E402
from rag_core.ike.infrastructure.issues_acl import issue_view  # noqa: E402
from rag_core.ike.infrastructure.retrieval_acl import RetrieverKnowledgeSearch  # noqa: E402
from rag_core.issues.application.services import load_issue_registry  # noqa: E402
from rag_core.issues.infrastructure.hierarchy_acl import HierarchyOrgDirectory  # noqa: E402
from rag_core.judging.application.services import LlmJudge, judge_all  # noqa: E402
from rag_core.judging.domain.cases import JudgeCase  # noqa: E402
from rag_core.judging.domain.metrics import (
    acceptance,
    agreement,
    gold_metrics,
    rejection_rate,
)  # noqa: E402
from rag_core.judging.domain.model import JudgeParseError  # noqa: E402
from rag_core.judging.domain.negative import negative_controls  # noqa: E402
from rag_core.judging.domain.parser import JudgeOutputParser  # noqa: E402
from rag_core.judging.domain.results import JudgeResult  # noqa: E402
from rag_core.judging.domain.rubric import Rubric, default_rubric  # noqa: E402
from rag_core.judging.domain.rule_judge import RuleBasedJudge  # noqa: E402
from rag_core.judging.infrastructure.calibration_json import (
    load_calibration,
    load_parser_cases,
)  # noqa: E402
from rag_core.judging.infrastructure.config import JudgeSettings, load_judge_settings  # noqa: E402
from rag_core.judging.infrastructure.ike_acl import summary_case  # noqa: E402
from rag_core.judging.infrastructure.prompt_yaml import load_judge_prompts, load_rubric  # noqa: E402
from rag_core.judging.infrastructure.qa_acl import (
    chunk_texts,
    phase8_cases,
    samples_by_id,
)  # noqa: E402
from rag_core.judging.infrastructure.results_files import latest_result, read_json  # noqa: E402
from rag_core.qa.domain.fact_check import CitedFactValidator  # noqa: E402
from rag_core.rag.application.corpus import build_corpus_records  # noqa: E402
from rag_core.rag.application.indexing import build_retriever  # noqa: E402
from rag_core.rag.infrastructure.config import RagSettings, load_settings  # noqa: E402
from rag_core.rag.infrastructure.ollama import (
    OllamaChatModel,
    OllamaClient,
    OllamaError,
)  # noqa: E402
from rag_core.rag.infrastructure.sqlite_store import SqliteIndexStore  # noqa: E402

KIT = f"rag-core {__version__} (phase 10 llm-as-judge)"
SEPARATOR_START = "======== PHASE 10 SUMMARY ========"
SEPARATOR_END = "======== END PHASE 10 SUMMARY ========"
CASE = "AR-ISS-024"
TOP_K = 8
BLIND_SPOT = "rule_blind_spot"


def find_root(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.resolve()
    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents, ROOT_CANDIDATE]:
        if (candidate / "pyproject.toml").is_file() and (
            candidate / "config" / "judge.yaml"
        ).is_file():
            return candidate
    raise SystemExit(
        "could not find the repo root (pyproject.toml + config/judge.yaml)"
    )


def parse_prior(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in filter(None, (p.strip() for p in text.split(","))):
        name, _, code = part.partition("=")
        out[name.strip()] = code.strip() or "?"
    return out


def rubric_matches_default(rubric: Rubric) -> bool:
    ref = default_rubric()
    return (rubric.out_of, rubric.accept_total, rubric.maximums, rubric.minimums) == (
        ref.out_of,
        ref.accept_total,
        ref.maximums,
        ref.minimums,
    )


def run_parser_cases(parser: JudgeOutputParser, cases: list[dict]) -> list[dict]:  # noqa: ANN001
    rows = []
    for c in cases:
        expect = c["expect"]
        row: dict[str, object] = {"id": c["id"], "note": c.get("note", "")}
        try:
            parsed = parser.parse(c["raw"])
        except JudgeParseError as exc:
            row.update(mode="error", ok=bool(expect.get("error")), detail=str(exc))
            rows.append(row)
            continue
        ok = not expect.get("error")
        ok = ok and parsed.scores == expect.get("scores")
        ok = ok and ("mode" not in expect or parsed.mode == expect["mode"])
        ok = ok and list(parsed.missing) == list(expect.get("missing", []))
        ok = ok and all(
            any(w in got for got in parsed.warnings)
            for w in expect.get("warnings_contain", [])
        )
        row.update(mode=parsed.mode, ok=ok, parsed=parsed.to_dict())
        rows.append(row)
    return rows


def mode_counts(rows: list[dict]) -> dict[str, int]:  # noqa: ANN001
    out: dict[str, int] = {}
    for r in rows:
        out[str(r["mode"])] = out.get(str(r["mode"]), 0) + 1
    return out


def ike_material(root: Path, settings: RagSettings, corpus) -> dict:  # noqa: ANN001
    """Phase 9 offline IKE graph of AR-ISS-024 → facts, names and template summaries."""
    teams = HierarchyTeamDirectory.from_registry(root / "data" / "registry")
    org = HierarchyOrgDirectory.from_registry(root / "data" / "registry")
    loaded = load_executor_registry(root / "data" / "executors", teams)
    executors = loaded.executors
    issues = load_issue_registry(root / "data" / "issues", org).issues
    case = next((i for i in issues if str(i.identifier) == CASE), None)
    if case is None or not executors:
        raise RuntimeError(f"{CASE} or the executor registry is missing")
    plans = ExecutorMatchingService(loaded.repository()).plans(referral_requests(case))
    view = issue_view(case)
    referrals = referrals_by_item(plans, executors)
    names = executor_names(executors)
    lexical = build_retriever(
        corpus.records, scope=corpus.scope, config=settings.retrieval
    )
    ike = IkeService(
        RetrieverKnowledgeSearch(lexical, corpus.scope),
        top_k=TOP_K,
        min_lexical=settings.qa.evidence_min_lexical,
        min_vector=settings.qa.evidence_min_vector,
    )
    graph = ike.build(view, referrals, ike.compare(view))
    summaries = IkeSummaryService(CitedFactValidator())
    facts = summaries.facts(view, graph, names)
    templates = {
        lang: summaries.template(view, graph, names, lang).text for lang in ("fa", "en")
    }
    return {"facts": facts, "names": names, "templates": templates}


def source_records(root: Path, settings: RagSettings, corpus) -> tuple[list, str]:  # noqa: ANN001
    """Chunk records for source text: the Phase 8 index if it exists, else the corpus build."""
    index_path = root / settings.index.path
    if index_path.is_file():
        try:
            with SqliteIndexStore(index_path) as store:
                records = store.records()
            if records:
                return records, f"index:{settings.index.path}"
        except Exception:  # noqa: BLE001 - fall back to the corpus build
            pass
    return list(corpus.records), "corpus"


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


def p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(
        ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))], 3
    )


def by_id(results: list[JudgeResult]) -> dict[str, JudgeResult]:
    return {r.case_id: r for r in results}


def main() -> int:  # noqa: C901 - one linear report
    parser = argparse.ArgumentParser(
        description="Phase 10 LLM-as-judge and quality control."
    )
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument(
        "--config", type=Path, default=None, help="config/rag.yaml (Ollama endpoint)"
    )
    parser.add_argument(
        "--judge-config", type=Path, default=None, help="config/judge.yaml"
    )
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--phase8-results", type=Path, default=None, help="folder with rag-demo-*.json"
    )
    parser.add_argument(
        "--phase9-results", type=Path, default=None, help="folder with ike-check-*.json"
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
    out_dir = args.out or root / "results" / "phase-10"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_json = out_dir / f"judge-check-{stamp}.json"
    t0 = time.perf_counter()

    # ---- rubric, prompts, parser
    rubric = load_rubric(root / jset.files.rubric)
    prompts = load_judge_prompts(root / jset.files.prompt_dir)
    calibration = load_calibration(root / jset.files.calibration)
    output_parser = JudgeOutputParser(rubric)
    parser_rows = run_parser_cases(
        output_parser, load_parser_cases(root / jset.files.parser_cases)
    )

    # ---- rule judge: calibration
    validator = CitedFactValidator()
    rule = RuleBasedJudge(rubric, validator, jset.rules)
    cal_rule = judge_all(rule, calibration)
    cal_rule_check = gold_metrics(cal_rule, exclude_tags=(BLIND_SPOT,))
    cal_rule_all = gold_metrics(cal_rule)
    blind = [r for r in cal_rule if BLIND_SPOT in r.tags]

    # ---- key outputs: Phase 9 templates (always), Phase 8 / Phase 9 live outputs (if present)
    corpus = build_corpus_records(root)
    ike_error = ""
    ike: dict = {}
    try:
        ike = ike_material(root, settings, corpus)
    except Exception as exc:  # noqa: BLE001 - reported as a failed check
        ike_error = f"{type(exc).__name__}: {exc}"
    template_cases: list[JudgeCase] = []
    if ike:
        template_cases = [
            summary_case(
                f"P9-TEMPLATE-{lang}",
                lang,
                text,
                ike["facts"],
                ike["names"],
                issue_id=CASE,
                origin="ike-template",
            )
            for lang, text in ike["templates"].items()
        ]

    # ---- every prompt renders for a real case of its kind (summaries: the Phase 9 templates)
    render_errors: list[str] = []
    for kind, prompt in prompts.items():
        sample = next(
            (c for c in calibration + template_cases if c.kind.value == kind), None
        )
        if sample is None:
            render_errors.append(f"{kind}: no case to render")
            continue
        try:
            prompt.render(
                sample, rubric, sources_char_budget=jset.run.sources_char_budget
            )
        except Exception as exc:  # noqa: BLE001 - reported as a failed check
            render_errors.append(f"{kind}: {exc}")

    p8_dir = args.phase8_results or root / jset.files.phase8_results
    p8_file = latest_result(p8_dir, "rag-demo-*.json")
    p8_info: dict[str, object] = {
        "file": str(p8_file) if p8_file else None,
        "status": "missing",
    }
    p8_cases: list[JudgeCase] = []
    if p8_file is not None:
        live8 = read_json(p8_file).get("live") or {}
        p8_info["status"] = live8.get("status", "missing")
        answers = live8.get("answers") or []
        if live8.get("status") == "ok" and answers:
            records, src = source_records(root, settings, corpus)
            samples = samples_by_id(root / "data" / "rag" / "sample-questions.json")
            p8_cases, missing = phase8_cases(answers, samples, chunk_texts(records))
            p8_info.update(sources=src, missing_chunks=missing, answers=len(p8_cases))

    p9_dir = args.phase9_results or root / jset.files.phase9_results
    p9_file = latest_result(p9_dir, "ike-check-*.json")
    p9_info: dict[str, object] = {
        "file": str(p9_file) if p9_file else None,
        "status": "missing",
    }
    p9_cases: list[JudgeCase] = []
    if p9_file is not None and ike:
        live9 = read_json(p9_file).get("live") or {}
        p9_info["status"] = live9.get("status", "missing")
        facts9 = live9.get("facts")
        if live9.get("status") == "ok" and facts9:
            for lang, s in (live9.get("summaries") or {}).items():
                if lang in {"fa", "en"} and str(s.get("text", "")).strip():
                    p9_cases.append(
                        summary_case(
                            f"P9-LLM-{lang}",
                            lang,
                            str(s["text"]),
                            list(facts9),
                            ike["names"],
                            issue_id=CASE,
                            origin="ike-llm",
                        )
                    )
            p9_info["summaries"] = len(p9_cases)
        elif live9.get("status") == "ok":
            p9_info["status"] = "ok-without-facts"

    key_cases = p8_cases + template_cases + p9_cases
    key_rule = judge_all(rule, key_cases)
    templates_rule = [r for r in key_rule if r.origin == "ike-template"]

    # ---- negative controls (rule judge). The PASS check uses only the offline ones
    # (calibration + templates); negatives made from live outputs are reported.
    neg_cal = negative_controls(calibration)
    neg_tpl = negative_controls(template_cases)
    neg_live_src = negative_controls(p8_cases) + negative_controls(p9_cases)
    neg_key = negative_controls(p8_cases) + neg_tpl + negative_controls(p9_cases)
    neg_rule = judge_all(rule, neg_cal + neg_tpl + neg_live_src)
    offline_neg_ids = {c.case_id for c in neg_cal + neg_tpl}
    neg_rule_offline = [r for r in neg_rule if r.case_id in offline_neg_ids]
    neg_rule_live_src = [r for r in neg_rule if r.case_id not in offline_neg_ids]

    # ---- live step
    live: dict[str, object] = {"status": "skipped", "reason": "disabled with --no-live"}
    ollama_info: dict[str, object] = {"base_url": settings.ollama.base_url}
    if not args.no_live:
        client, reason, ollama_info = probe_ollama(settings, jset.model.model)
        if client is None:
            live = {"status": "skipped", "reason": reason}
        else:
            print(
                "live step: Ollama",
                ollama_info.get("version"),
                "→ qwen3:8b as judge",
                flush=True,
            )
            try:
                live = {
                    "status": "ok",
                    **live_step(
                        jset,
                        settings,
                        client,
                        rubric,
                        prompts,
                        key_cases,
                        calibration,
                        neg_key,
                        key_rule,
                        neg_rule,
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
    neg_rejected = sum(1 for r in neg_rule_offline if not r.accepted)
    checks = {
        "pytest": args.pytest_exit in (None, "0", 0),
        "prior_steps": all(v == "0" for v in prior.values()),
        "rubric_valid": rubric_matches_default(rubric),
        "prompts_render": not render_errors
        and set(prompts) == {"qa_answer", "qa_refusal", "ike_summary"},
        "parser_cases": bool(parser_rows) and all(r["ok"] for r in parser_rows),
        "calibration_rule_agrees": cal_rule_check["n"] > 0
        and cal_rule_check["agree"] == cal_rule_check["n"],
        "negative_controls_rejected": bool(neg_rule_offline)
        and neg_rejected == len(neg_rule_offline),
        "ike_templates_accepted": len(templates_rule) == 2
        and all(r.accepted for r in templates_rule),
        "records_built": bool(corpus.records) and not corpus.failures,
    }
    status = "PASS" if all(checks.values()) else "FAIL"

    payload = {
        "kit": KIT,
        "run_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": status,
        "checks": checks,
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
        "rubric": rubric.to_dict(),
        "prompts": {k: v.label for k, v in prompts.items()},
        "prompt_render_errors": render_errors,
        "judge_model": {
            "model": jset.model.model,
            "think": jset.model.think,
            "format": jset.model.format,
            "options": jset.model.options,
        },
        "ollama": ollama_info,
        "parser_cases": parser_rows,
        "calibration_rule": {
            "check": cal_rule_check,
            "all": cal_rule_all,
            "results": [r.to_dict() for r in cal_rule],
        },
        "phase8_results": p8_info,
        "phase9_results": p9_info,
        "ike_error": ike_error,
        "ike_facts": ike.get("facts", []),
        "key_outputs_rule": {
            "acceptance": acceptance(key_rule),
            "results": [r.to_dict() for r in key_rule],
        },
        "negative_controls_rule": {
            "offline": rejection_rate(neg_rule_offline),
            "from_live_outputs": rejection_rate(neg_rule_live_src),
            "results": [r.to_dict() for r in neg_rule],
            "cases": [
                {"case_id": c.case_id, "output": c.output}
                for c in neg_cal + neg_tpl + neg_live_src
            ],
        },
        "live": live,
        "total_seconds": round(total_s, 2),
    }
    out_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

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
    print(
        f"rubric: {rubric.label} out_of={rubric.out_of} accept>={rubric.accept_total} min="
        + ",".join(f"{c.key}:{c.min_points}/{c.max_points}" for c in rubric.criteria)
    )
    seen: dict[str, list[str]] = {}
    for kind, p in prompts.items():
        seen.setdefault(p.label, []).append(kind)
    print(
        "prompts: "
        + " ".join(f"{label}({','.join(kinds)})" for label, kinds in seen.items())
        + (f" render_errors={len(render_errors)}" if render_errors else "")
    )
    print(
        f"parser_cases: ok={sum(1 for r in parser_rows if r['ok'])}/{len(parser_rows)} modes="
        + ",".join(f"{k}:{v}" for k, v in mode_counts(parser_rows).items())
    )
    for r in parser_rows:
        if not r["ok"]:
            print(f"  - {r['id']} ({r['note']}): mode={r['mode']} MISMATCH")
    blind_txt = ",".join(f"{r.case_id}:{r.decision.value}" for r in blind) or "-"
    print(
        f"calibration_rule: cases={cal_rule_all['n']} agree={cal_rule_all['agree']}/{cal_rule_all['n']} "
        f"positives_accepted={cal_rule_all['positives_accepted']}/{cal_rule_all['positives']} "
        f"negatives_rejected={cal_rule_all['negatives_rejected']}/{cal_rule_all['negatives']} "
        f"blind_spots={blind_txt} check={cal_rule_check['agree']}/{cal_rule_check['n']}"
    )
    for d in cal_rule_check["disagreements"]:
        print(f"  - disagreement: {d}")
    nr = rejection_rate(neg_rule_offline)
    nl = rejection_rate(neg_rule_live_src)
    print(
        f"negative_controls_rule: offline_rejected={nr['rejected']}/{nr['n']} "
        f"from_live_outputs_rejected={nl['rejected']}/{nl['n']} by_kind="
        + ",".join(
            f"{k}:{v['rejected']}/{v['n']}"
            for k, v in rejection_rate(neg_rule)["by_kind"].items()
        )
    )
    for a in nr["accepted_cases"] + nl["accepted_cases"]:
        print(f"  - accepted negative: {a}")
    print(
        "ike_templates_rule: "
        + (
            " ".join(
                f"{r.case_id.rsplit('-', 1)[1]}={r.total}/{r.outcome.out_of}:"
                f"{r.decision.value}"
                for r in templates_rule
            )
            or f"none ({ike_error})"
        )
    )
    p8_rule = [r for r in key_rule if r.origin == "phase8-live"]
    if p8_rule:
        a8 = acceptance(p8_rule)
        print(
            f"phase8_answers_rule: file={Path(str(p8_info['file'])).name} answers={a8['n']} "
            f"accepted={a8['accepted']}/{a8['n']} mean_total={a8['mean_total']} sources={p8_info.get('sources')} "
            f"rejected={','.join(a8['rejected_cases']) or '-'}"
        )
    else:
        print(f"phase8_answers_rule: none (phase 8 live results: {p8_info['status']})")
    p9_rule = [r for r in key_rule if r.origin == "ike-llm"]
    if p9_rule:
        print(
            f"phase9_summaries_rule: file={Path(str(p9_info['file'])).name} "
            + " ".join(
                f"{r.case_id.rsplit('-', 1)[1]}={r.total}/{r.outcome.out_of}:{r.decision.value}"
                for r in p9_rule
            )
        )
    else:
        print(
            f"phase9_summaries_rule: none (phase 9 live results: {p9_info['status']})"
        )
    ka = acceptance(key_rule)
    print(
        f"key_outputs_rule: accepted={ka['accepted']}/{ka['n']} rate={ka['rate']} (accept >= "
        f"{rubric.accept_total}/{rubric.out_of} and every criterion >= its minimum)"
    )
    print(
        f"live: {live['status']}"
        + (f" ({live.get('reason')})" if live.get("reason") else "")
    )
    if live["status"] == "ok":
        print_live(live, rubric)
    print(
        "checks: " + " ".join(f"{k}={'ok' if v else 'FAIL'}" for k, v in checks.items())
    )
    shown = out_json.resolve()
    shown = (
        shown.relative_to(root.resolve())
        if shown.is_relative_to(root.resolve())
        else out_json
    )
    print(f"results_json: {shown}")
    print(SEPARATOR_END)
    return 0 if status == "PASS" else 1


def live_step(
    jset: JudgeSettings,
    settings: RagSettings,
    client: OllamaClient,
    rubric: Rubric,
    prompts: dict,
    key_cases: list[JudgeCase],
    calibration: list[JudgeCase],
    negatives: list[JudgeCase],
    key_rule: list[JudgeResult],
    neg_rule: list[JudgeResult],
) -> dict:
    m = jset.model
    chat = OllamaChatModel(
        client,
        m.model,
        dict(m.options),
        m.think,
        m.keep_alive,
        m.timeout_s,
        response_format=m.format or None,
    )
    judge = LlmJudge(
        rubric,
        prompts,
        chat,
        name=f"llm:{m.model}",
        retries=jset.run.retries,
        sources_char_budget=jset.run.sources_char_budget,
    )
    cases = list(key_cases)
    if jset.run.live_calibration:
        cases += calibration
    if jset.run.live_negatives:
        cases += negatives
    capped = len(cases) > jset.run.max_live_cases
    cases = cases[: jset.run.max_live_cases]

    def progress(i: int, n: int, r: JudgeResult) -> None:
        print(
            f"  [{i}/{n}] {r.case_id}: {r.total}/{r.outcome.out_of} {r.decision.value}",
            flush=True,
        )

    t0 = time.perf_counter()
    results = judge_all(judge, cases, progress=progress)
    seconds = time.perf_counter() - t0
    key_ids = {c.case_id for c in key_cases}
    cal_ids = {c.case_id for c in calibration}
    neg_ids = {c.case_id for c in negatives}
    key = [r for r in results if r.case_id in key_ids]
    cal = [r for r in results if r.case_id in cal_ids]
    neg = [r for r in results if r.case_id in neg_ids]
    rule_by_id = by_id(key_rule)
    combined = [
        r
        for r in key
        if r.accepted
        and rule_by_id.get(r.case_id) is not None
        and rule_by_id[r.case_id].accepted
    ]
    modes: dict[str, int] = {}
    for r in results:
        modes[r.parse_mode] = modes.get(r.parse_mode, 0) + 1
    times = [r.seconds for r in results if r.parse_mode != "error" or r.seconds]
    return {
        "judge": judge.name,
        "cases": len(cases),
        "capped": capped,
        "calls": sum(r.attempts for r in results),
        "retried": sum(1 for r in results if r.attempts > 1),
        "errors": sum(1 for r in results if r.decision.value == "error"),
        "parse_modes": modes,
        "key_outputs": acceptance(key),
        "key_combined_with_rule": {"accepted": len(combined), "n": len(key)},
        "key_agreement_with_rule": agreement(key, key_rule),
        "calibration": gold_metrics(cal),
        "calibration_blind_spots": [r.to_dict() for r in cal if BLIND_SPOT in r.tags],
        "negative_controls": rejection_rate(neg),
        "negative_agreement_with_rule": agreement(neg, neg_rule),
        "criterion_means": acceptance(results)["criterion_means"],
        "timings": {
            "judge_avg_s": round(sum(times) / len(times), 3) if times else None,
            "judge_p95_s": p95(times),
            "total_s": round(seconds, 1),
        },
        "tokens": {
            "prompt_avg": round(sum(r.prompt_tokens for r in results) / len(results))
            if results
            else None,
            "completion_avg": round(
                sum(r.completion_tokens for r in results) / len(results)
            )
            if results
            else None,
        },
        "results": [r.to_dict() for r in results],
        "rule_totals": {r.case_id: r.total for r in key_rule},
    }


def print_live(live: dict, rubric: Rubric) -> None:
    ko = live["key_outputs"]
    comb = live["key_combined_with_rule"]
    agr = live["key_agreement_with_rule"]
    print(
        f"live_judge: {live['judge']} think=off format=json cases={live['cases']} calls={live['calls']} "
        f"retried={live['retried']} errors={live['errors']} modes="
        + ",".join(f"{k}:{v}" for k, v in live["parse_modes"].items())
        + (" CAPPED" if live["capped"] else "")
    )
    print(
        f"live_key_outputs: accepted={ko['accepted']}/{ko['n']} rate={ko['rate']} mean_total={ko['mean_total']} "
        f"min_total={ko['min_total']} combined_with_rule={comb['accepted']}/{comb['n']} "
        f"agreement_with_rule={agr['agree']}/{agr['n']} kappa={agr['kappa']}"
    )
    rule_totals = live["rule_totals"]
    for r in live["results"]:
        if r["origin"] in {"phase8-live", "ike-template", "ike-llm"}:
            print(
                f"  {r['case_id']}: llm={r['total']}/{r['out_of']} {r['decision']} rule={rule_totals.get(r['case_id'])}"
                + (f" reasons={';'.join(r['reasons'])}" if r["reasons"] else "")
            )
    cal = live["calibration"]
    if cal["n"]:
        blind = (
            ",".join(
                f"{b['case_id']}:{b['decision']}({b['total']})"
                for b in live["calibration_blind_spots"]
            )
            or "-"
        )
        print(
            f"live_calibration: agree={cal['agree']}/{cal['n']} positives_accepted={cal['positives_accepted']}/"
            f"{cal['positives']} negatives_rejected={cal['negatives_rejected']}/{cal['negatives']} "
            f"blind_spot={blind}"
        )
        for d in cal["disagreements"]:
            print(f"  - disagreement: {d}")
    neg = live["negative_controls"]
    if neg["n"]:
        print(
            f"live_negative_controls: rejected={neg['rejected']}/{neg['n']} rate={neg['rate']} by_kind="
            + ",".join(
                f"{k}:{v['rejected']}/{v['n']}" for k, v in neg["by_kind"].items()
            )
        )
        for a in neg["accepted_cases"]:
            print(f"  - accepted negative: {a}")
    print(
        "live_criterion_means: "
        + " ".join(
            f"{k}={v}/{rubric.maximums[k]}" for k, v in live["criterion_means"].items()
        )
    )
    t = live["timings"]
    tok = live["tokens"]
    print(
        f"live_timings: judge_avg_s={t['judge_avg_s']} judge_p95_s={t['judge_p95_s']} "
        f"tokens_avg={tok['prompt_avg']}+{tok['completion_avg']} total_s={t['total_s']}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
