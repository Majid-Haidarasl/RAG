#!/usr/bin/env python3
"""Phase 8: RAG retrieval core & node-scoped Q&A — offline check + live demo.

Always (no Ollama needed):
* Builds index records from the official corpus (Phase 4 ingest, Phase 5
  lifecycle, Phase 6 owners/layers) and checks the scope filter.
* Offline dry run: lexical-only retrieval for the sample questions
  (``data/rag/sample-questions.json``) → hit@5 / MRR / outside detection.

Live (only if local Ollama answers and bge-m3 + qwen3:8b are installed):
* Builds or refreshes the persistent index (``.rag-index/phase-08.sqlite``);
  only new or changed chunks are embedded.
* Asks the sample questions through ``NodeScopedQaService`` and reports
  hit@5 / MRR, citation validity, out-of-scope handling, fact-check flags
  and timings. Without Ollama the live step prints SKIPPED with the reason.

The overall status depends on pytest, the earlier steps and the offline
check only; the live step is reported separately (live: ok/skipped/fail).
Prints the ``PHASE 8 SUMMARY`` block and writes
``results/phase-08/rag-demo-<UTC>.json``.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

ROOT_CANDIDATE = Path(__file__).resolve().parents[1]
_src = ROOT_CANDIDATE / "src"
if _src.is_dir() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from rag_core import __version__
from rag_core.qa.application.evaluation import (
    facts_found,
    load_samples,
    qa_metrics,
    retrieval_metrics,
)
from rag_core.qa.application.service import NodeScopedQaService, QaConfig
from rag_core.qa.domain.model import QaRequest
from rag_core.qa.infrastructure.prompt_yaml import load_qa_prompts
from rag_core.rag.application.corpus import build_corpus_records
from rag_core.rag.application.indexing import IndexBuilder, build_retriever
from rag_core.rag.domain.context import ContextAssembler
from rag_core.rag.infrastructure.config import RagSettings, load_settings
from rag_core.rag.infrastructure.ollama import (
    OllamaChatModel,
    OllamaClient,
    OllamaEmbedder,
    OllamaError,
)
from rag_core.rag.infrastructure.sqlite_store import SqliteIndexStore

KIT = f"rag-core {__version__} (phase 8 rag + qa)"
SEPARATOR_START = "======== PHASE 8 SUMMARY ========"
SEPARATOR_END = "======== END PHASE 8 SUMMARY ========"


def find_root(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.resolve()
    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents, ROOT_CANDIDATE]:
        if (candidate / "pyproject.toml").is_file() and (
            candidate / "config" / "rag.yaml"
        ).is_file():
            return candidate
    raise SystemExit("could not find the repo root (pyproject.toml + config/rag.yaml)")


def parse_prior(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in filter(None, (p.strip() for p in text.split(","))):
        name, _, code = part.partition("=")
        out[name.strip()] = code.strip() or "?"
    return out


def offline_check(root: Path, settings: RagSettings, samples) -> dict:
    corpus = build_corpus_records(root)
    records = corpus.records
    retriever = build_retriever(records, scope=corpus.scope, config=settings.retrieval)
    rows = []
    scope_violations = 0
    for s in samples:
        res = retriever.retrieve(s.question, s.node)
        visible = corpus.scope.visible_documents(s.node)
        scope_violations += sum(
            1 for h in res.hits if h.record.document_id not in visible
        )
        rows.append((s, res))
    metrics = retrieval_metrics(rows)
    # Sample sanity: every expected fact group occurs in an expected document.
    text_by_doc: dict[str, str] = {}
    for r in records:
        if r.is_active:
            text_by_doc[r.document_id] = (
                text_by_doc.get(r.document_id, "") + "\n" + r.text
            )
    facts_ok = 0
    facts_total = 0
    for s in samples:
        if s.expected_docs and s.expected_facts:
            facts_total += 1
            hit, total = facts_found(
                " ".join(text_by_doc.get(d, "") for d in s.expected_docs),
                s.expected_facts,
            )
            facts_ok += hit == total
    active = [r for r in records if r.is_active]
    langs: dict[str, int] = {}
    for r in active:
        langs[r.language] = langs.get(r.language, 0) + 1
    return {
        "corpus": {
            "files": corpus.files,
            "failures": corpus.failures,
            "records": len(records),
            "active": len(active),
            "active_by_language": langs,
            "exact_duplicates_marked": sum(1 for r in records if r.duplicate_of),
            "documents": len({r.document_id for r in records}),
            "with_paragraph_anchor": sum(1 for r in records if r.paragraph is not None),
            "seconds": round(corpus.seconds, 3),
        },
        "lexical_dry_run": metrics.to_dict(),
        "per_question": [
            {
                "id": s.id,
                "node": s.node,
                "top_docs": r.document_ids()[:5],
                "outside_owners": sorted({e.owner_node for e in r.out_of_scope}),
                "duplicates_dropped": len(r.duplicates_dropped),
            }
            for s, r in rows
        ],
        "checks": {
            "records_built": len(active) > 0 and not corpus.failures,
            "scope_respected": scope_violations == 0,
            "samples_consistent": facts_ok == facts_total,
        },
        "_corpus": corpus,
    }


def probe_ollama(settings: RagSettings) -> tuple[OllamaClient | None, str, dict]:
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
    missing = [
        m
        for m in (settings.embedding.model, settings.generation.model)
        if not OllamaClient.has_model(names, m)
    ]
    if missing:
        return (
            None,
            "model(s) not installed: "
            + ", ".join(missing)
            + " (run: ollama pull "
            + " && ollama pull ".join(missing)
            + ")",
            info,
        )
    return client, "", info


def live_step(
    root: Path,
    settings: RagSettings,
    samples,
    corpus,
    client: OllamaClient,
    rebuild: bool,
) -> dict:
    prompts = load_qa_prompts(root / settings.qa.prompt_dir, settings.qa.prompt_id)
    embedder = OllamaEmbedder(
        client,
        settings.embedding.model,
        settings.embedding.batch_size,
        settings.embedding.num_ctx,
        settings.ollama.keep_alive,
        settings.ollama.embed_timeout_s,
    )
    index_path = root / settings.index.path
    if rebuild and index_path.exists():
        index_path.unlink()
    with SqliteIndexStore(index_path) as store:

        def progress(done: int, total: int) -> None:
            if done == total or done % (settings.embedding.batch_size * 10) == 0:
                print(f"  embedded {done}/{total}", flush=True)

        build = IndexBuilder(
            store, embedder, settings.embedding.model, settings.embedding.batch_size
        ).refresh(corpus.records, progress)
        vectors = store.load_vectors(settings.embedding.model)
    if vectors.dim != settings.embedding.dim:
        raise OllamaError(
            f"embedding dim {vectors.dim} != configured {settings.embedding.dim}"
        )
    retriever = build_retriever(
        corpus.records,
        vectors=vectors,
        embedder=embedder,
        scope=corpus.scope,
        config=settings.retrieval,
    )
    chat = OllamaChatModel(
        client,
        settings.generation.model,
        dict(settings.generation.options),
        settings.generation.think,
        settings.ollama.keep_alive,
        settings.ollama.generate_timeout_s,
    )
    service = NodeScopedQaService(
        retriever,
        ContextAssembler(
            settings.context.budget_tokens, settings.context.max_block_tokens
        ),
        chat,
        prompts,
        config=QaConfig(
            settings.qa.evidence_min_vector,
            settings.qa.evidence_min_lexical,
            settings.qa.escalate_margin,
        ),
        model_name=settings.generation.model,
    )
    rrows = []
    qrows = []
    answers = []
    for s in samples:
        print(f"  {s.id} [{s.node}] {s.question[:60]}", flush=True)
        res = retriever.retrieve(s.question, s.node)
        ans = service.ask(QaRequest(s.question, s.node))
        rrows.append((s, res))
        qrows.append((s, ans))
        answers.append(
            {
                "id": s.id,
                "expected_status": s.expected_status,
                "expected_docs": list(s.expected_docs),
                "retrieval": [h.to_dict() for h in res.hits],
                "out_of_scope_probe": [
                    {
                        "document_id": e.document_id,
                        "owner": e.owner_node,
                        "vector": None
                        if e.vector_score is None
                        else round(e.vector_score, 4),
                    }
                    for e in res.out_of_scope
                ],
                **ans.to_dict(),
            }
        )
    rm = retrieval_metrics(rrows)
    qm = qa_metrics(qrows)
    return {
        "index": build.to_dict(),
        "retrieval": rm.to_dict(),
        "qa": qm.to_dict(),
        "per_question": qm.per_question,
        "answers": answers,
        "prompt": f"{prompts.prompt_id}@{prompts.version}",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Phase 8 RAG offline check + live demo."
    )
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--questions", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="drop the index and embed everything again",
    )
    parser.add_argument("--no-live", action="store_true", help="skip the Ollama step")
    for name in ("passed", "failed", "errors", "skipped", "exit", "line"):
        parser.add_argument(f"--pytest-{name}", default=None)
    parser.add_argument("--python-version", default=None)
    parser.add_argument("--prior", default="", help="earlier steps as name=exit,...")
    args = parser.parse_args()

    root = find_root(args.root)
    settings = load_settings(args.config or root / "config" / "rag.yaml")
    samples = load_samples(
        args.questions or root / "data" / "rag" / "sample-questions.json"
    )
    out_dir = args.out or root / "results" / "phase-08"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_json = out_dir / f"rag-demo-{stamp}.json"

    t0 = time.perf_counter()
    offline = offline_check(root, settings, samples)
    corpus = offline.pop("_corpus")

    live: dict[str, object] = {"status": "skipped", "reason": "disabled with --no-live"}
    ollama_info: dict[str, object] = {"base_url": settings.ollama.base_url}
    if not args.no_live:
        client, reason, ollama_info = probe_ollama(settings)
        if client is None:
            live = {"status": "skipped", "reason": reason}
        else:
            print(
                "live step: Ollama",
                ollama_info.get("version"),
                "→ building index and asking samples",
                flush=True,
            )
            try:
                live = {
                    "status": "ok",
                    **live_step(root, settings, samples, corpus, client, args.rebuild),
                }
            except Exception as exc:  # noqa: BLE001 - the live step never breaks the kit status
                live = {
                    "status": "fail",
                    "reason": f"{type(exc).__name__}: {exc}",
                    "traceback": traceback.format_exc(limit=5),
                }
    total_s = time.perf_counter() - t0

    prior = parse_prior(args.prior)
    pytest_ok = args.pytest_exit in (None, "0", 0)
    prior_ok = all(v == "0" for v in prior.values())
    checks = {"pytest": pytest_ok, "prior_steps": prior_ok, **offline["checks"]}
    status = "PASS" if all(checks.values()) else "FAIL"

    payload = {
        "kit": KIT,
        "run_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
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
        "models": {
            "embedding": settings.embedding.model,
            "generation": settings.generation.model,
            "think": settings.generation.think,
            "options": settings.generation.options,
        },
        "ollama": ollama_info,
        "settings": {
            "retrieval": settings.retrieval.__dict__,
            "context": settings.context.__dict__,
            "qa": settings.qa.__dict__,
            "embedding_batch": settings.embedding.batch_size,
            "timeouts_s": {
                "embed": settings.ollama.embed_timeout_s,
                "generate": settings.ollama.generate_timeout_s,
            },
        },
        "offline": offline,
        "live": live,
        "total_seconds": round(total_s, 2),
    }
    out_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    c = offline["corpus"]
    lx = offline["lexical_dry_run"]
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
        f"models: embedding={settings.embedding.model} generation={settings.generation.model} "
        f"think={'on' if settings.generation.think else 'off'} temperature={settings.generation.options.get('temperature')}"
    )
    print(
        f"ollama: {settings.ollama.base_url} version={ollama_info.get('version', '-')}"
    )
    print(
        f"index_records: files={c['files']} records={c['records']} active={c['active']} "
        f"fa={c['active_by_language'].get('fa', 0)} en={c['active_by_language'].get('en', 0)} "
        f"exact_dups_marked={c['exact_duplicates_marked']} build_s={c['seconds']}"
    )
    print(
        f"retrieval: hybrid BM25 + cosine, RRF k={settings.retrieval.rrf_k}, top_k={settings.retrieval.top_k}, "
        f"context_budget={settings.context.budget_tokens} tokens"
    )
    print(
        f"offline_lexical_dry_run: hit@5={lx['hit_at_5']} mrr={lx['mrr']} (n={lx['scored']}) "
        f"outside_detected={lx['outside_detected']}"
    )
    print(
        f"live: {live['status']}"
        + (f" ({live.get('reason')})" if live.get("reason") else "")
    )
    if live["status"] == "ok":
        ix = live["index"]  # type: ignore[index]
        rm = live["retrieval"]  # type: ignore[index]
        qm = live["qa"]  # type: ignore[index]
        print(
            f"live_index: active={ix['active']} embedded={ix['embedded']} reused={ix['reused']} removed={ix['removed']} "
            f"dim={ix['dim']} batches={ix['batches']} build_s={ix['seconds']} embed_s={ix['embed_seconds']}"
        )
        print(
            f"live_retrieval: hit@5={rm['hit_at_5']} mrr={rm['mrr']} (n={rm['scored']}) outside_detected={rm['outside_detected']}"
        )
        print(
            f"live_qa: status_ok={qm['status_ok']}/{qm['questions']} answered={qm['answered']} grounded={qm['grounded']} "
            f"citation_validity={qm['citation_validity']} ({qm['citations_valid']}/{qm['citations_total']}) "
            f"scope_handling={qm['scope_handling']} facts={qm['facts']} fact_flags={qm['fact_flags']}"
        )
        print(
            f"live_timings: retrieval_avg_s={qm['retrieval_avg_s']} generation_avg_s={qm['generation_avg_s']} "
            f"generation_p95_s={qm['generation_p95_s']} total_s={round(total_s, 1)}"
        )
        for row in live["per_question"]:  # type: ignore[union-attr]
            print(
                f"  {row['id']}: {row['status']} ok={row['status_ok']} cites={row['citations']} facts={row['facts']} "
                f"flags={row['fact_flags']}"
                + (f" escalate->{row['escalation']}" if row["escalation"] else "")
            )
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


if __name__ == "__main__":
    raise SystemExit(main())
