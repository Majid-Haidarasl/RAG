#!/usr/bin/env python3
"""Phase 14: prompt testing, model tuning and sample evaluation.

Always (no Ollama needed):
* Loads the bilingual gold set (eval/datasets/armanrayan-qa.jsonl: 16 pairs,
  Persian + English), validates it (facts in the reference answers, labels,
  partial answers, refusals, pairs) and grounds it in the real corpus: every
  evidence quote is in its document, every fact is in the quotes and the
  reference answers add no number or id. Checks the node scope and that all
  ten Phase 8 sample questions are covered.
* Compares the retrieval variants of config/eval.yaml with BM25 only:
  hit@1/3/5, MRR and the share of reference facts that reach the answer
  context (the Phase 8 Q06 diagnosis line shows the list question).
* Expands the Phase 10 judge calibration set from 14 to 42 cases (a reference
  answer and one broken answer per gold pair) and checks it with the rule judge.
* Renders the tuned prompts (Q&A, strict judge with a checklist, id-list
  prompts), runs the required-id controls and checks that every variant
  choice in config/eval.yaml exists and has a written reason.

Live (only if local Ollama answers and the models are installed):
* Hybrid retrieval (bge-m3 + BM25) per variant, reusing the Phase 8 index.
* qa.answer vs qa.answer_complete on all 32 gold questions (qwen3:8b, think
  off): status, facts, grounding, citations, rule-judge acceptance, length.
* Baseline vs strict LLM judge on the 42 calibration cases: agreement with
  gold, kappa, leniency (gold rejects accepted), rejection by mutation, time.
* The Phase 13 AI texts (newest results/phase-13/rfp-check-*.json) with the
  baseline prompt, the id-list prompt and the id-list prompt with one retry.
* The measured winner per kind next to the configured choice.

The status depends on pytest, the earlier steps and the offline checks only.
Prints the ``PHASE 14 SUMMARY`` block and writes
``eval/results/phase-14-check-<UTC>.json`` and ``updated-metrics-<UTC>.md``.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
import traceback
from typing import Any

ROOT_CANDIDATE = Path(__file__).resolve().parents[1]
_src = ROOT_CANDIDATE / "src"
if _src.is_dir() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))
_scripts = Path(__file__).resolve().parent
if str(_scripts) not in sys.path:
    sys.path.insert(0, str(_scripts))

from run_project_check import parse_prior, probe_ollama, rel  # noqa: E402

from rag_core import __version__  # noqa: E402
from rag_core.judging.application.services import LlmJudge, judge_all  # noqa: E402
from rag_core.judging.domain.rule_judge import RuleBasedJudge  # noqa: E402
from rag_core.judging.domain.text import language_matches  # noqa: E402
from rag_core.judging.infrastructure.calibration_json import load_calibration  # noqa: E402
from rag_core.judging.infrastructure.config import JudgeSettings, load_judge_settings  # noqa: E402
from rag_core.judging.infrastructure.prompt_yaml import load_judge_prompts, load_rubric  # noqa: E402
from rag_core.judging.infrastructure.qa_acl import chunk_texts, phase8_cases  # noqa: E402
from rag_core.qa.application.evaluation import facts_found, load_samples, status_ok  # noqa: E402
from rag_core.qa.application.service import NodeScopedQaService, QaConfig  # noqa: E402
from rag_core.qa.domain.fact_check import CitedFactValidator  # noqa: E402
from rag_core.qa.domain.model import QaRequest, QaStatus  # noqa: E402
from rag_core.qa.infrastructure.prompt_yaml import load_qa_prompts  # noqa: E402
from rag_core.rag.application.corpus import build_corpus_records  # noqa: E402
from rag_core.rag.application.indexing import IndexBuilder, build_retriever  # noqa: E402
from rag_core.rag.infrastructure.config import RagSettings, load_settings  # noqa: E402
from rag_core.rag.infrastructure.ollama import OllamaChatModel, OllamaClient, OllamaEmbedder, OllamaError  # noqa: E402
from rag_core.rag.infrastructure.sqlite_store import SqliteIndexStore  # noqa: E402
from rag_core.rfp.domain.advice import ReplyParseError, check_reply, parse_reply  # noqa: E402
from rag_core.rfp.infrastructure.config import RfpSettings, load_rfp_settings  # noqa: E402
from rag_core.rfp.infrastructure.judging_acl import feedback_task, rfp_task, summary_case  # noqa: E402
from rag_core.rfp.infrastructure.prompts_yaml import load_rfp_prompts, prompt_set  # noqa: E402
from rag_core.shared_kernel.errors import DomainError  # noqa: E402
from rag_core.tuning.application.services import (  # noqa: E402
    Generated,
    IdVariantRunner,
    answer_row,
    choose,
    compare_retrieval,
    id_candidates,
    judge_candidates,
    judge_report,
    retrieval_candidates,
    summarize_prompt,
)
from rag_core.tuning.domain.gold import pairs, phase8_coverage, validate_gold  # noqa: E402
from rag_core.tuning.domain.required_ids import (  # noqa: E402
    IdVariant,
    id_checklist,
    missing_ids,
    retry_note,
    summarize_id_runs,
)
from rag_core.tuning.domain.variants import Candidate, selection_problems  # noqa: E402
from rag_core.tuning.infrastructure.config import EvalSettings, load_eval_settings  # noqa: E402
from rag_core.tuning.infrastructure.gold_jsonl import load_gold  # noqa: E402
from rag_core.tuning.infrastructure.ids_acl import IdJob, load_jobs, render_job  # noqa: E402
from rag_core.tuning.infrastructure.judging_acl import (  # noqa: E402
    MUTATIONS,
    derive_calibration,
    load_strict_prompts,
)
from rag_core.tuning.infrastructure.rag_acl import (  # noqa: E402
    CachingEmbedder,
    assembler,
    document_texts,
    gold_grounding,
    rank_items,
    retrieval_config,
    scope_problems,
    to_sample,
)

KIT = f"rag-core {__version__} (phase 14 prompt testing, model tuning, sample evaluation)"
SEPARATOR_START = "======== PHASE 14 SUMMARY ========"
SEPARATOR_END = "======== END PHASE 14 SUMMARY ========"
LOAD_ERRORS = (DomainError, ValueError, KeyError, TypeError, OSError)
Q06_ITEMS = ("GQ-P06-fa", "GQ-P06-en")


def find_root(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.resolve()
    for cand in (Path.cwd(), ROOT_CANDIDATE):
        if (cand / "pyproject.toml").is_file() and (cand / "config" / "eval.yaml").is_file():
            return cand.resolve()
    return ROOT_CANDIDATE


def f3(value: float | None) -> str:
    return "-" if value is None else f"{value:.3f}"


def fs(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


# ---- offline pieces ---------------------------------------------------------------------------------
def lexical_rank(records, scope, settings: RagSettings, eset: EvalSettings, items):  # noqa: ANN001, ANN201
    """Variant id -> ranking rows with BM25 only (vector weights have no effect here)."""
    def rank(variant_id: str):  # noqa: ANN202
        v = eset.variant(variant_id)
        retriever = build_retriever(records, scope=scope, config=retrieval_config(v, settings.retrieval))
        asm = assembler(v, settings.context.max_block_tokens)

        def one(item):  # noqa: ANN001, ANN202
            result = retriever.retrieve(item.question, item.node, probe_outside=False)
            return result, asm.assemble(result.hits).text
        return rank_items(items, one, scope)
    return rank


def q06_line(summaries: dict) -> str:  # noqa: ANN001
    parts = []
    for vid, s in summaries.items():
        rows = {r.item_id: r for r in s.rows}
        bits = [f"{i[-2:]}:rank={rows[i].first_rank or '-'},facts={rows[i].context_facts[0]}/{rows[i].context_facts[1]}"
                for i in Q06_ITEMS if i in rows]
        parts.append(f"{vid}(" + " ".join(bits) + ")")
    return " ".join(parts)


class FakeIdModel:
    """Offline stand-in for the id test: the first text drops the last required id, a retry names all."""

    def __call__(self, job: IdJob, variant: str, note: str) -> Generated:
        ids = list(job.required)
        named = ids if note else ids[:-1]
        return Generated("; ".join(named) + ".", grounded=True)


def ids_controls(root: Path, eset: EvalSettings, rset: RfpSettings) -> dict[str, Any]:
    """Prompt rendering + id helpers + the retry loop with a fake model (no Ollama)."""
    out: dict[str, Any] = {"problems": []}
    job_fa = IdJob("rfp_summary", "AR-RFP-TEST", "fa", ("fact line [AR-ISS-024]",),
                   ("AR-ISS-024", "AR-ISS-024/WEB", "AR-ISS-024/WIN"), ("AR-ISS-024/WEB",))
    job_en = IdJob("feedback", "PRP-TEST", "en", ("fact line [AR-ISS-024]",), ("PRP-TEST", "AR-ISS-024"), ())
    try:
        baseline_dir = root / rset.storage.prompt_dir
        base = load_rfp_prompts(baseline_dir)
        listed = {t: prompt_set(_yaml(root / eset.files.ids_prompt_dir / f"{t}.yaml"), f"{t}.yaml")
                  for t in ("rfp_summary", "feedback")}
        baseline = {"rfp_summary": base.rfp_summary, "feedback": base.feedback}
        rendered = 0
        for job in (job_fa, job_en):
            for v in eset.id_variants:
                system, user = render_job(job, v, baseline, listed)  # type: ignore[arg-type]
                rendered += 1
                if "{" + "facts}" in user or "{" + "checklist}" in user:
                    out["problems"].append(f"placeholder_left:{job.task}:{v}")
                if v != IdVariant.BASELINE and id_checklist(job.required) not in user:
                    out["problems"].append(f"checklist_missing:{job.task}:{v}")
        out["rendered"] = rendered
        out["prompts"] = {t: f"{p.prompt_id}@{p.version}" for t, p in listed.items()}
    except LOAD_ERRORS as exc:
        out["problems"].append(f"prompts:{type(exc).__name__}: {exc}")
    text = "خلاصه با AR-ISS-024 و AR-ISS-024/WEB"
    if missing_ids(text, job_fa.required) != ("AR-ISS-024/WIN",):
        out["problems"].append("missing_ids")
    note = retry_note(("AR-ISS-024/WIN",), "fa")
    if "AR-ISS-024/WIN" not in note or "AR-ISS-024/WIN" not in retry_note(("AR-ISS-024/WIN",), "en"):
        out["problems"].append("retry_note")
    runner = IdVariantRunner(FakeIdModel(), lambda job, text: (True, None))
    rows = runner.run_all([job_fa, job_en], [v.value for v in IdVariant])
    summary = summarize_id_runs(rows)
    out["fake_runs"] = summary
    if summary.get("listed_retry", {}).get("all_ids") != 2 or summary.get("listed", {}).get("all_ids") != 0:
        out["problems"].append("retry_loop")
    out["ok"] = not out["problems"]
    return out


def _yaml(path: Path) -> dict[str, Any]:
    import yaml
    with Path(path).open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must be a mapping")
    return data


# ---- live pieces ------------------------------------------------------------------------------------
class Budget:
    def __init__(self, generations: int, judge_calls: int) -> None:
        self.generations = generations
        self.judge_calls = judge_calls
        self.skipped: list[str] = []

    def take(self, kind: str, n: int, what: str) -> bool:
        left = getattr(self, kind)
        if n > left:
            self.skipped.append(f"{what} (needs {n}, {left} left)")
            return False
        setattr(self, kind, left - n)
        return True


def chat_for(client: OllamaClient, settings: RagSettings, model: str) -> OllamaChatModel:
    g = settings.generation
    return OllamaChatModel(client, model, dict(g.options), g.think, settings.ollama.keep_alive,
                           settings.ollama.generate_timeout_s)


def live_vectors(root: Path, settings: RagSettings, client: OllamaClient, records):  # noqa: ANN001, ANN201
    e = settings.embedding
    embedder = OllamaEmbedder(client, e.model, e.batch_size, e.num_ctx, settings.ollama.keep_alive,
                              settings.ollama.embed_timeout_s)
    index_path = root / settings.index.path
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with SqliteIndexStore(index_path) as store:
        report = IndexBuilder(store, embedder, e.model, e.batch_size).refresh(records)
        vectors = store.load_vectors(e.model)
    if vectors.dim != e.dim:
        raise OllamaError(f"embedding dim {vectors.dim} != configured {e.dim}")
    return vectors, CachingEmbedder(embedder), {"embedded": report.embedded, "seconds": round(report.seconds, 1)}


def live_retrieval(records, scope, vectors, embedder, settings: RagSettings, eset: EvalSettings, items):  # noqa: ANN001, ANN201
    def rank(variant_id: str):  # noqa: ANN202
        v = eset.variant(variant_id)
        retriever = build_retriever(records, vectors=vectors, embedder=embedder, scope=scope,
                                    config=retrieval_config(v, settings.retrieval))
        asm = assembler(v, settings.context.max_block_tokens)

        def one(item):  # noqa: ANN001, ANN202
            result = retriever.retrieve(item.question, item.node, probe_outside=False)
            return result, asm.assemble(result.hits).text
        return rank_items(items, one, scope)
    return compare_retrieval([v.id for v in eset.retrieval_variants], rank)


def live_qa(root: Path, settings: RagSettings, client: OllamaClient, records, scope, vectors, embedder,  # noqa: ANN001
            eset: EvalSettings, items, rule_judge: RuleBasedJudge, budget: Budget) -> dict[str, Any]:
    v = eset.variant(eset.chosen("retrieval")) if "retrieval" in eset.selection else eset.retrieval_variants[0]
    retriever = build_retriever(records, vectors=vectors, embedder=embedder, scope=scope,
                                config=retrieval_config(v, settings.retrieval))
    texts = chunk_texts(records)
    samples = {i.id: to_sample(i) for i in items}
    q = settings.qa
    out: dict[str, Any] = {"retrieval_variant": v.id, "runs": {}}
    for model in eset.live.generation_models:
        chat = chat_for(client, settings, model)
        for prompt_id in eset.qa_prompts:
            key = prompt_id if model == settings.generation.model else f"{prompt_id}@{model}"
            if not budget.take("generations", len(items), f"qa {key}"):
                continue
            prompts = load_qa_prompts(root / q.prompt_dir, prompt_id)
            service = NodeScopedQaService(retriever, assembler(v, settings.context.max_block_tokens), chat, prompts,
                                          config=QaConfig(q.evidence_min_vector, q.evidence_min_lexical,
                                                          q.escalate_margin), model_name=model)
            rows = []
            answers = []
            for n, item in enumerate(items, 1):
                ans = service.ask(QaRequest(item.question, item.node))
                d = ans.to_dict()
                d.update({"id": item.id, "expected_status": item.expected_status})
                judged = None
                if item.answered:
                    cases, _missing = phase8_cases([d], samples, texts)
                    judged = judge_all(rule_judge, cases)[0].accepted
                found = facts_found(ans.text, item.expected_facts) if ans.status is QaStatus.ANSWERED \
                    else (0, len(item.expected_facts))
                rows.append(answer_row(item.id, item.detail, d, status_ok=status_ok(samples[item.id], ans),
                                       facts=found, rule_accepted=judged))
                answers.append({"id": item.id, "status": d["status"], "text": d["text"],
                                "facts": f"{found[0]}/{found[1]}", "rule_accepted": judged,
                                "timings_s": d["timings_s"]})
                if n % 8 == 0:
                    print(f"  qa {key}: {n}/{len(items)}", flush=True)
            summary = summarize_prompt(key, rows)
            out["runs"][key] = {"prompt": f"{prompts.prompt_id}@{prompts.version}", "model": model,
                                **summary.to_dict(), "answers": answers}
    return out


def live_judges(root: Path, jset: JudgeSettings, eset: EvalSettings, client: OllamaClient, rubric, cases,  # noqa: ANN001
                budget: Budget) -> dict[str, Any]:
    jm = jset.model
    chat = OllamaChatModel(client, jm.model, dict(jm.options), jm.think, jm.keep_alive, jm.timeout_s,
                           response_format=jm.format or None)
    prompt_sets = {"baseline": load_judge_prompts(root / jset.files.prompt_dir),
                   "strict": load_strict_prompts(root / eset.files.strict_judge_dir)}
    out: dict[str, Any] = {"model": jm.model, "reports": {}, "results": {}}
    for variant in eset.judge_prompts:
        if not budget.take("judge_calls", len(cases), f"judge {variant}"):
            continue
        judge = LlmJudge(rubric, prompt_sets[variant], chat, name=f"llm:{variant}", retries=jset.run.retries,
                         sources_char_budget=jset.run.sources_char_budget)
        t0 = time.perf_counter()
        results = judge_all(judge, cases, progress=lambda i, n, r, v=variant: print(
            f"  judge {v}: {i}/{n}", flush=True) if i % 14 == 0 else None)
        report = judge_report(variant, results)
        out["reports"][variant] = {**report.to_dict(), "total_s": round(time.perf_counter() - t0, 1)}
        out["results"][variant] = [{"case_id": r.case_id, "gold": r.gold, "accepted": r.accepted, "total": r.total,
                                    "decision": r.decision.value, "seconds": round(r.seconds, 2)} for r in results]
        out.setdefault("_objects", {})[variant] = report
    return out


def live_ids(root: Path, eset: EvalSettings, rset: RfpSettings, client: OllamaClient, rubric, jset: JudgeSettings,  # noqa: ANN001
             validator: CitedFactValidator, budget: Budget) -> dict[str, Any]:
    jobs, path = load_jobs(root / eset.files.phase13_results, rset.live.languages)
    if not jobs:
        return {"status": "skipped", "reason": "no results/phase-13/rfp-check-*.json with AI-text jobs (run Phase 13)"}
    m = rset.model
    chat = OllamaChatModel(client, m.model, dict(m.options), m.think, m.keep_alive, m.timeout_s,
                           response_format=m.format or None)
    base = load_rfp_prompts(root / rset.storage.prompt_dir)
    baseline = {"rfp_summary": base.rfp_summary, "feedback": base.feedback}
    listed = {t: prompt_set(_yaml(root / eset.files.ids_prompt_dir / f"{t}.yaml"), f"{t}.yaml")
              for t in ("rfp_summary", "feedback")}
    rule = RuleBasedJudge(rubric, validator, jset.rules)
    replies: list[dict[str, Any]] = []

    def generate(job: IdJob, variant: str, note: str) -> Generated:
        system, user = render_job(job, variant, baseline, listed)  # type: ignore[arg-type]
        if note:
            user = f"{user}\n\n{note}"
        try:
            res = chat.generate(system, user)
            parsed = parse_reply(res.text or "", job.reply_key)
        except ReplyParseError as exc:
            replies.append({"job": job.label, "variant": variant, "retry": bool(note), "error": str(exc)})
            return Generated(error=str(exc))
        except OllamaError as exc:
            return Generated(error=f"{type(exc).__name__}: {exc}")
        check = check_reply(parsed, job.facts, job.items, validator)
        replies.append({"job": job.label, "variant": variant, "retry": bool(note), "text": parsed.text,
                        "missing": list(missing_ids(parsed.text, job.required))})
        return Generated(parsed.text, grounded=check.grounded, invented=check.invented_ids)

    def accept(job: IdJob, text: str) -> tuple[bool, int | None]:
        task = rfp_task(job.subject, job.language) if job.task == "rfp_summary" else feedback_task(job.subject,
                                                                                                    job.language)
        case = summary_case(f"P14-{job.task}-{job.subject}-{job.language}", job.language, task, text, job.facts,
                            job.items, job.gaps, origin="rfp-ai")
        r = judge_all(rule, [case])[0]
        return r.accepted, r.total

    variants = list(eset.id_variants)
    need = len(jobs) * (len(variants) + (1 if IdVariant.LISTED_RETRY.value in variants else 0))
    if not budget.take("generations", need, "ids"):
        return {"status": "skipped", "reason": "generation cap reached"}
    runner = IdVariantRunner(generate, accept)
    rows = runner.run_all(jobs, variants, progress=lambda r: print(
        f"  ids {r.task} {r.subject} {r.language} {r.variant}: {r.mentioned}/{r.expected}"
        f" {'accepted' if r.accepted else 'rejected'}", flush=True))
    return {"status": "ok", "source": rel(root, path) if path else None, "jobs": len(jobs),
            "summary": summarize_id_runs(rows), "rows": [r.to_dict() for r in rows], "replies": replies,
            "_rows": rows}


# ---- report -----------------------------------------------------------------------------------------
def metrics_markdown(payload: dict[str, Any]) -> str:
    """Short markdown table set of one run (eval/results/updated-metrics-<UTC>.md)."""
    lines = [f"# Phase 14 measured metrics — {payload['run_at']}", "",
             f"Kit: {payload['kit']} · status: {payload['status']} · live: {payload['live'].get('status')}", ""]
    lines += ["## Retrieval (offline, BM25)", "", "| variant | hit@1 | hit@3 | hit@5 | MRR | context facts |",
              "|---|---|---|---|---|---|"]
    for vid, s in (payload.get("retrieval_offline") or {}).items():
        lines.append(f"| {vid} | {s['hit_at_1']} | {s['hit_at_3']} | {s['hit_at_5']} | {s['mrr']} | "
                     f"{s['context_facts_count']} |")
    live = payload.get("live") or {}
    if live.get("retrieval"):
        lines += ["", "## Retrieval (live, BM25 + bge-m3)", "", "| variant | hit@1 | hit@5 | MRR | context facts |",
                  "|---|---|---|---|---|"]
        for vid, s in live["retrieval"].items():
            lines.append(f"| {vid} | {s['hit_at_1']} | {s['hit_at_5']} | {s['mrr']} | {s['context_facts_count']} |")
    if (live.get("qa") or {}).get("runs"):
        lines += ["", f"## Q&A prompts (live, retrieval variant {live['qa']['retrieval_variant']})", "",
                  "| prompt | status ok | facts | grounded | citations | rule accept | detail ok | gen avg s |",
                  "|---|---|---|---|---|---|---|---|"]
        for key, r in live["qa"]["runs"].items():
            lines.append(f"| {key} | {r['status_ok']} | {r['facts']} | {r['grounded']} | {r['citations']} | "
                         f"{r['rule_accepted']} | {r['detail_ok']} | {r['generation_avg_s']} |")
    if (live.get("judge") or {}).get("reports"):
        lines += ["", "## LLM judge (live, 42 calibration cases)", "",
                  "| prompt | accuracy | kappa | leniency | errors | avg s |", "|---|---|---|---|---|---|"]
        for key, r in live["judge"]["reports"].items():
            a = r["agreement"]
            lines.append(f"| {key} | {a['accuracy']} | {a['kappa']} | {a['leniency']} | {r['errors']} | {r['avg_s']} |")
    if (live.get("ids") or {}).get("summary"):
        lines += ["", "## Required ids (live, Phase 13 AI texts)", "",
                  "| variant | ids named | all ids | accepted | retries | avg s |", "|---|---|---|---|---|---|"]
        for key, r in live["ids"]["summary"].items():
            lines.append(f"| {key} | {r['mentioned']} | {r['all_ids']}/{r['n']} | {r['accepted']}/{r['n']} | "
                         f"{r['retries']} | {r['seconds_avg']} |")
    lines += ["", "## Choices", "", "| kind | configured | measured winner | agrees |", "|---|---|---|---|"]
    for c in payload.get("choices") or []:
        m = c.get("measured") or {}
        lines.append(f"| {c['kind']} | {c['configured']} | {m.get('winner', '-')} ({m.get('reason', 'not measured')}) "
                     f"| {c['agrees']} |")
    return "\n".join(lines) + "\n"


def main() -> int:  # noqa: C901 - one linear check script, like the earlier phases
    parser = argparse.ArgumentParser(description="Phase 14 prompt testing, model tuning and sample evaluation.")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--config", type=Path, default=None, help="config/rag.yaml (Ollama endpoint, models)")
    parser.add_argument("--judge-config", type=Path, default=None, help="config/judge.yaml")
    parser.add_argument("--rfp-config", type=Path, default=None, help="config/rfp.yaml")
    parser.add_argument("--eval-config", type=Path, default=None, help="config/eval.yaml")
    parser.add_argument("--out", type=Path, default=None, help="folder for phase-14-check-*.json")
    parser.add_argument("--no-live", action="store_true", help="skip the Ollama step")
    for name in ("passed", "failed", "errors", "skipped", "exit", "line"):
        parser.add_argument(f"--pytest-{name}", default=None)
    parser.add_argument("--python-version", default=None)
    parser.add_argument("--prior", default="", help="earlier steps as name=exit,...")
    args = parser.parse_args()

    root = find_root(args.root)
    settings: RagSettings = load_settings(args.config or root / "config" / "rag.yaml")
    jset: JudgeSettings = load_judge_settings(args.judge_config or root / "config" / "judge.yaml")
    rset: RfpSettings = load_rfp_settings(args.rfp_config or root / "config" / "rfp.yaml")
    eset: EvalSettings = load_eval_settings(args.eval_config or root / "config" / "eval.yaml")
    out_dir = args.out or root / eset.files.results_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_json = out_dir / f"phase-14-check-{stamp}.json"
    out_md = out_dir / f"updated-metrics-{stamp}.md"
    t0 = time.perf_counter()
    errors: list[str] = []

    # ---- gold set
    items: list = []
    try:
        items = load_gold(root / eset.files.dataset)
    except LOAD_ERRORS as exc:
        errors.append(f"gold: {type(exc).__name__}: {exc}")
    gold_problems = validate_gold(items, facts_found, language_matches) if items else []
    by_pair = pairs(items)
    try:
        phase8_ids = [s.id for s in load_samples(root / "data" / "rag" / "sample-questions.json")]
    except LOAD_ERRORS as exc:
        errors.append(f"samples: {type(exc).__name__}: {exc}")
        phase8_ids = []
    covered, wanted, not_covered = phase8_coverage(items, phase8_ids)

    # ---- corpus, grounding, scope
    corpus = build_corpus_records(root)
    records = corpus.records
    if corpus.failures:
        errors.append(f"corpus: {len(corpus.failures)} file(s) failed")
    validator = CitedFactValidator()
    grounding = gold_grounding(items, document_texts(records), validator) if items else []
    scope_issues = scope_problems(items, corpus.scope) if items else ["no items"]

    # ---- retrieval variants, offline
    answered = [i for i in items if i.answered]
    offline = compare_retrieval([v.id for v in eset.retrieval_variants],
                                lexical_rank(records, corpus.scope, settings, eset, answered)) if answered else {}

    # ---- calibration
    rubric = load_rubric(root / jset.files.rubric)
    rule_judge = RuleBasedJudge(rubric, validator, jset.rules)
    base_cases: list = []
    try:
        base_cases = load_calibration(root / eset.files.calibration)
    except LOAD_ERRORS as exc:
        errors.append(f"calibration: {type(exc).__name__}: {exc}")
    derived = derive_calibration(items) if items else []
    cases = [*base_cases, *(d.case for d in derived)]
    if len({c.case_id for c in cases}) != len(cases):
        errors.append("calibration: duplicate case ids")
    rule_results = judge_all(rule_judge, cases) if cases else []
    rule_rep = judge_report("rule", rule_results)
    rule_by_id = {r.case_id: r for r in rule_results}
    derived_ok = [d for d in derived if not d.mutation]
    derived_bad = [d for d in derived if d.mutation]
    ok_accepted = sum(1 for d in derived_ok if rule_by_id[d.case.case_id].accepted)
    bad_rejected = sum(1 for d in derived_bad if not rule_by_id[d.case.case_id].accepted)
    kinds_seen = sorted({d.mutation for d in derived_bad})
    blind = [c.case_id for c in base_cases if "rule_blind_spot" in c.tags]
    base_wrong = [cid for cid in rule_rep.wrong if not cid.startswith("CAL14-")]

    # ---- prompts render
    render_problems: list[str] = []
    rendered = 0
    qa_labels: list[str] = []
    try:
        judge_sets = {"baseline": load_judge_prompts(root / jset.files.prompt_dir),
                      "strict": load_strict_prompts(root / eset.files.strict_judge_dir)}
        for variant in eset.judge_prompts:
            for c in cases:
                system, user = judge_sets[variant][c.kind.value].render(
                    c, rubric, sources_char_budget=jset.run.sources_char_budget)
                rendered += 1
                if "${" in system + user:
                    render_problems.append(f"{variant}:{c.case_id}:placeholder")
                if variant == "strict" and "1. " not in user:
                    render_problems.append(f"strict:{c.case_id}:no_checklist")
        for pid in eset.qa_prompts:
            p = load_qa_prompts(root / settings.qa.prompt_dir, pid)
            qa_labels.append(f"{p.prompt_id}@{p.version}")
            for item in items[:2]:
                p.render(question=item.question, context="[AR-SW-022 §1]\ntext", language=item.language,
                         node=item.node)
                rendered += 1
    except LOAD_ERRORS as exc:
        render_problems.append(f"{type(exc).__name__}: {exc}")
    ids_ctl = ids_controls(root, eset, rset)

    # ---- selection
    sel_problems = selection_problems(eset.selection, eset.known_variants())
    retrieval_pick = choose("retrieval", eset.selection["retrieval"].variant if "retrieval" in eset.selection else "",
                            retrieval_candidates(offline), eset.selection_rules.get("retrieval"), "baseline")

    # ---- live step
    live: dict[str, Any] = {"status": "skipped", "reason": "disabled with --no-live"}
    ollama_info: dict[str, Any] = {"base_url": settings.ollama.base_url}
    choices = []
    if not args.no_live and not eset.live.enabled:
        live = {"status": "skipped", "reason": "live.enabled is false in config/eval.yaml"}
    elif not args.no_live:
        client, reason, ollama_info = probe_ollama(settings, settings.generation.model)
        if client is not None and not OllamaClient.has_model(ollama_info.get("models") or [], settings.embedding.model):
            client, reason = None, f"model not installed: {settings.embedding.model}"
        if client is None:
            live = {"status": "skipped", "reason": reason}
        else:
            print("live step: Ollama", ollama_info.get("version"), "-> hybrid retrieval, Q&A prompts, judges, ids",
                  flush=True)
            budget = Budget(eset.live.max_generations, eset.live.max_judge_calls)
            live = {"status": "ok"}
            try:
                t1 = time.perf_counter()
                vectors, embedder, index_info = live_vectors(root, settings, client, records)
                live["index"] = index_info
                live_ret = live_retrieval(records, corpus.scope, vectors, embedder, settings, eset, answered)
                live["retrieval"] = {k: v.to_dict() for k, v in live_ret.items()}
                live["q06"] = q06_line(live_ret)
                retrieval_pick = choose("retrieval", eset.chosen("retrieval"), retrieval_candidates(live_ret),
                                        eset.selection_rules.get("retrieval"), "baseline")
                live["timings"] = {"retrieval_s": round(time.perf_counter() - t1, 1)}
                extra = [m for m in eset.live.generation_models
                         if m != settings.generation.model and not OllamaClient.has_model(ollama_info["models"], m)]
                if extra:
                    live["models_missing"] = extra
                    eset_models = tuple(m for m in eset.live.generation_models if m not in extra)
                else:
                    eset_models = eset.live.generation_models
                if eset.live.qa:
                    t1 = time.perf_counter()
                    from dataclasses import replace as _replace
                    qa_eset = _replace(eset, live=_replace(eset.live, generation_models=eset_models))
                    live["qa"] = live_qa(root, settings, client, records, corpus.scope, vectors, embedder, qa_eset,
                                         items, rule_judge, budget)
                    live["timings"]["qa_s"] = round(time.perf_counter() - t1, 1)
                if eset.live.judge:
                    t1 = time.perf_counter()
                    live["judge"] = live_judges(root, jset, eset, client, rubric, cases, budget)
                    live["timings"]["judge_s"] = round(time.perf_counter() - t1, 1)
                if eset.live.ids:
                    t1 = time.perf_counter()
                    live["ids"] = live_ids(root, eset, rset, client, rubric, jset, validator, budget)
                    live["timings"]["ids_s"] = round(time.perf_counter() - t1, 1)
                live["budget_skipped"] = budget.skipped
            except Exception as exc:  # noqa: BLE001 - the live step never breaks the kit status
                live = {**live, "status": "fail", "reason": f"{type(exc).__name__}: {exc}",
                        "traceback": traceback.format_exc(limit=5)}
    choices.append(retrieval_pick)
    qa_runs = (live.get("qa") or {}).get("runs") or {}
    qa_cands = [Candidate(k, r["metrics"]) for k, r in qa_runs.items() if k in eset.qa_prompts]
    choices.append(choose("qa_prompt", eset.chosen("qa_prompt"), qa_cands, eset.selection_rules.get("qa_prompt"),
                          eset.qa_prompts[0]))
    judge_objs = (live.get("judge") or {}).pop("_objects", {}) if live.get("judge") else {}
    choices.append(choose("judge_prompt", eset.chosen("judge_prompt"), judge_candidates(judge_objs),
                          eset.selection_rules.get("judge_prompt"), "baseline"))
    id_rows = (live.get("ids") or {}).pop("_rows", []) if live.get("ids") else []
    choices.append(choose("ai_ids", eset.chosen("ai_ids"), id_candidates(id_rows), eset.selection_rules.get("ai_ids"),
                          IdVariant.BASELINE.value))
    total_s = time.perf_counter() - t0

    # ---- checks
    prior = parse_prior(args.prior)
    base_off = offline.get("baseline")
    checks = {
        "pytest": args.pytest_exit in (None, "0", 0),
        "prior_steps": all(v == "0" for v in prior.values()),
        "gold_loaded": len(items) >= 30 and all(set(by) == {"fa", "en"} for by in by_pair.values())
        and not any(e.startswith(("gold", "samples")) for e in errors),
        "gold_valid": bool(items) and not gold_problems,
        "gold_grounded": bool(items) and not grounding and not corpus.failures,
        "gold_in_scope": bool(items) and not scope_issues,
        "phase8_covered": wanted > 0 and covered == wanted,
        "retrieval_offline": bool(offline) and base_off is not None
        and all(s.n == len(answered) and s.hit_at_5 is not None and s.scope_violations == 0 for s in offline.values()),
        "calibration_expanded": len(base_cases) == 14 and len(derived_ok) == len(derived_bad) == len(answered) // 2
        and set(kinds_seen) == set(MUTATIONS) and ok_accepted == len(derived_ok)
        and bad_rejected == len(derived_bad) and all(c in blind for c in base_wrong),
        "prompts_render": rendered > 0 and not render_problems,
        "ids_controls": bool(ids_ctl.get("ok")),
        "selection_documented": not sel_problems,
    }
    status = "PASS" if all(checks.values()) else "FAIL"

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
        "gold": {"items": len(items), "pairs": len(by_pair), "problems": [str(p) for p in gold_problems],
                 "grounding": [str(g) for g in grounding], "scope": scope_issues,
                 "phase8": f"{covered}/{wanted}", "phase8_missing": not_covered},
        "retrieval_offline": {k: v.to_dict() for k, v in offline.items()},
        "calibration": {"base": len(base_cases), "derived": len(derived), "total": len(cases),
                        "mutations": {k: sum(1 for d in derived_bad if d.mutation == k) for k in MUTATIONS},
                        "rule_judge": rule_rep.to_dict(), "derived_accepts": f"{ok_accepted}/{len(derived_ok)}",
                        "derived_rejects": f"{bad_rejected}/{len(derived_bad)}", "blind_spots": blind},
        "prompts": {"rendered": rendered, "problems": render_problems, "qa": qa_labels},
        "ids_controls": ids_ctl,
        "selection": {k: {"variant": s.variant, "reason": s.reason} for k, s in eset.selection.items()},
        "selection_problems": sel_problems,
        "choices": [c.to_dict() for c in choices],
        "ollama": ollama_info,
        "live": live,
        "timings": {"total_s": round(total_s, 2), "corpus_s": round(corpus.seconds, 2)},
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
    n_fa = sum(1 for i in items if i.language == "fa")
    print(f"gold: items={len(items)} pairs={len(by_pair)} fa={n_fa} en={len(items) - n_fa} answered={len(answered)} "
          f"refusals={len(items) - len(answered)} phase8={covered}/{wanted} new_pairs="
          f"{sum(1 for by in by_pair.values() if not any(i.phase8_id for i in by.values()))} "
          f"problems={len(gold_problems)} grounding={len(grounding)} scope={len(scope_issues)}"
          + (f" first={gold_problems[0]}" if gold_problems else "")
          + (f" first_grounding={grounding[0]}" if grounding else "")
          + (f" first_scope={scope_issues[0]}" if scope_issues else ""))
    for vid, s in offline.items():
        print(f"retrieval_offline: {vid} hit@1={f3(s.hit_at_1)} hit@3={f3(s.hit_at_3)} hit@5={f3(s.hit_at_5)} "
              f"mrr={f3(s.mrr)} context_facts={s.context_facts_hit}/{s.context_facts_total} "
              f"full={s.full_context}/{s.n} scope_violations={s.scope_violations}")
    if offline:
        print(f"q06_offline: {q06_line(offline)}")
    mut = ",".join(f"{k}:{sum(1 for d in derived_bad if d.mutation == k)}" for k in MUTATIONS)
    print(f"calibration: base={len(base_cases)} derived={len(derived)} total={len(cases)} mutations={mut}")
    a = rule_rep.agreement
    print(f"rule_judge: agreement={a.agree}/{a.n} kappa={f3(a.kappa)} leniency={f3(a.leniency)} "
          f"derived_accepts={ok_accepted}/{len(derived_ok)} derived_rejects={bad_rejected}/{len(derived_bad)} "
          f"base_wrong={','.join(base_wrong) or '-'} blind_spots={','.join(blind) or '-'}"
          + (f" by_mutation={','.join(f'{k}:{v}' for k, v in rule_rep.by_mutation.items())}"))
    print(f"prompts: rendered={rendered} problems={len(render_problems)} qa={','.join(qa_labels) or '-'} "
          f"judge={','.join(eset.judge_prompts)} ids={','.join((ids_ctl.get('prompts') or {}).values()) or '-'}"
          + (f" first={render_problems[0]}" if render_problems else ""))
    fake = ids_ctl.get("fake_runs") or {}
    print("ids_controls: " + ("ok" if ids_ctl.get("ok") else "FAIL " + ",".join(ids_ctl["problems"][:3]))
          + " fake_all_ids " + " ".join(f"{k}={v['all_ids']}/{v['n']}" for k, v in fake.items()))
    print("selection: " + " ".join(f"{k}={s.variant}" for k, s in eset.selection.items())
          + f" problems={len(sel_problems)}" + (f" first={sel_problems[0]}" if sel_problems else ""))
    print(f"live: {live['status']}" + (f" ({live.get('reason')})" if live.get("reason") else ""))
    if live.get("retrieval"):
        for vid, s in live["retrieval"].items():
            print(f"live_retrieval: {vid} hit@1={f3(s['hit_at_1'])} hit@5={f3(s['hit_at_5'])} mrr={f3(s['mrr'])} "
                  f"context_facts={s['context_facts_count']} full={s['full_context']}/{s['n']}")
        print(f"q06_live: {live.get('q06')}")
    for key, r in ((live.get("qa") or {}).get("runs") or {}).items():
        print(f"live_qa: {key} status_ok={r['status_ok']} facts={r['facts']} grounded={r['grounded']} "
              f"citations={r['citations']} rule_accepted={r['rule_accepted']} detail_ok={r['detail_ok']} "
              f"gen_avg_s={fs(r['generation_avg_s'])} gen_p95_s={fs(r['generation_p95_s'])}")
        q06 = [x for x in r["answers"] if x["id"] in Q06_ITEMS]
        if q06:
            print(f"  q06 {key}: " + " ".join(f"{x['id'][-2:]}={x['facts']}" for x in q06))
    for key, r in ((live.get("judge") or {}).get("reports") or {}).items():
        ag = r["agreement"]
        print(f"live_judge: {key} agreement={ag['agree']}/{ag['n']} kappa={f3(ag['kappa'])} "
              f"leniency={f3(ag['leniency'])} false_accepts={ag['false_accepts']} false_rejects={ag['false_rejects']} "
              f"errors={r['errors']} avg_s={fs(r['avg_s'])} by_mutation="
              + ",".join(f"{k}:{v}" for k, v in r["by_mutation"].items()))
    ids = live.get("ids") or {}
    if ids.get("status") == "ok":
        for key, r in ids["summary"].items():
            print(f"live_ids: {key} named={r['mentioned']} all_ids={r['all_ids']}/{r['n']} "
                  f"accepted={r['accepted']}/{r['n']} invented={r['invented_ids']} retries={r['retries']} "
                  f"avg_s={fs(r['seconds_avg'])}")
    elif ids:
        print(f"live_ids: {ids.get('status')} ({ids.get('reason')})")
    if live.get("budget_skipped"):
        print("live_budget_skipped: " + "; ".join(live["budget_skipped"]))
    if live.get("timings"):
        print("live_timings: " + " ".join(f"{k}={v}" for k, v in live["timings"].items()))
    for c in choices:
        m = c.measured
        print(f"choice: {c.kind} configured={c.configured} measured="
              + (f"{m.winner} ({m.reason})" if m is not None else "- (not measured)")
              + f" agrees={'-' if c.agrees is None else ('yes' if c.agrees else 'NO')}")
    print("checks: " + " ".join(f"{k2}={'ok' if v else 'FAIL'}" for k2, v in checks.items()))
    print(f"results_json: {rel(root, out_json)}")
    print(f"metrics_md: {rel(root, out_md)}")
    print(SEPARATOR_END)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
