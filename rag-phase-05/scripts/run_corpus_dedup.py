#!/usr/bin/env python3
"""Phase 5: ingest → knowledge lifecycle → duplicate detection on the real corpus.

* Official ``corpus/fa`` + ``corpus/en`` files are registered in the
  KnowledgeItem lifecycle (one item per document id, two language versions).
* ``corpus/derived`` renditions (PDF/DOC exports) only take part in dedup.
* A version update is simulated on a temporary, modified copy of
  AR-HW-012 (FA); the unchanged official file is re-ingested as well.
* Prints a ``PHASE 5 SUMMARY`` block and writes ``results/phase-05/dedup-<UTC>.json``.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time

ROOT_CANDIDATE = Path(__file__).resolve().parents[1]
_src = ROOT_CANDIDATE / "src"
if _src.is_dir() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from docx import Document  # noqa: E402

from rag_core.ingestion.application.pipeline import ingest_file  # noqa: E402
from rag_core.ingestion.domain.model import IngestedDocument  # noqa: E402
from rag_core.knowledge.application.lifecycle import KnowledgeLifecycleService  # noqa: E402
from rag_core.knowledge.domain.dedup import DedupConfig, DedupReport, DuplicateFinder, TextRecord  # noqa: E402
from rag_core.knowledge.domain.fingerprint import guess_language  # noqa: E402
from rag_core.knowledge.domain.model import ChunkStatus, VersionStatus  # noqa: E402
from rag_core.shared_kernel.identifiers import DocumentId  # noqa: E402

KIT = "rag-core 0.5.1 (phase 5)"
FORMATS = (".docx", ".doc", ".pdf")
SEPARATOR_START = "======== PHASE 5 SUMMARY (paste this block) ========"
SEPARATOR_END = "======== END PHASE 5 SUMMARY ========"
UPDATE_DOC = "AR-HW-012"
CORPUS_EFFECTIVE = date(2024, 10, 1)  # catalog: 1403-07 / 2024-10
UPDATE_EFFECTIVE = date(2026, 11, 11)  # 1405-08-20
UPDATE_PARAGRAPH = (
    "بازنگری ۱.۱ (شبیه‌سازی فاز ۵): مهلت عیب‌یابی اولیه دستگاه از سه روز کاری به دو روز کاری "
    "کاهش یافت و تأیید کتبی مشتری برای هر برآورد بالاتر از سقف ضمانت الزامی است."
)


def find_root(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.resolve()
    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents, ROOT_CANDIDATE]:
        if (candidate / "pyproject.toml").is_file() and (candidate / "corpus").is_dir():
            return candidate
    raise SystemExit("could not find the repo root (pyproject.toml + corpus/)")


def collect(corpus: Path, folder: str) -> list[Path]:
    base = corpus / folder
    if not base.exists():
        return []
    return [p for p in sorted(base.rglob("*")) if p.is_file() and p.suffix.lower() in FORMATS]


def rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root)) if path.is_relative_to(root) else str(path)


def to_records(docs: list[IngestedDocument], root: Path) -> tuple[list[TextRecord], list[TextRecord]]:
    chunk_records: list[TextRecord] = []
    doc_records: list[TextRecord] = []
    for doc in docs:
        source = rel(doc.path, root)
        lang = doc.language.value if doc.language else guess_language(doc.text)
        fmt = doc.file_format.value
        for chunk in doc.chunks:
            chunk_records.append(
                TextRecord(f"{source}::{chunk.chunk_id}", doc.document_id, lang, source, chunk.text, file_format=fmt)
            )
        if doc.text.strip():
            doc_records.append(TextRecord(source, doc.document_id, lang, source, doc.text, file_format=fmt))
    return chunk_records, doc_records


def pdf_quality(docs: list[IngestedDocument], failures: list[dict[str, str]], root: Path) -> dict[str, object]:
    """PDF text-quality tally (finding F5-1 and its 0.5.1 fix).

    ``garbled`` = PDFs whose text was rejected (GarbledTextError) or still
    contains cid placeholders; ``fragmented`` = readable PDFs with spurious
    intra-word spaces (warning only).
    """
    garbled: list[str] = [f["path"] for f in failures if f.get("error_type") == "GarbledTextError"]
    fragmented: list[str] = []
    engines: Counter[str] = Counter()
    for doc in docs:
        if doc.file_format.value != "pdf":
            continue
        engines[doc.extraction_engine or "unknown"] += 1
        verdict = (doc.text_quality or {}).get("verdict")
        if verdict == "garbled" or doc.text.count("(cid:") >= 20:
            garbled.append(rel(doc.path, root))
        elif verdict == "fragmented":
            fragmented.append(rel(doc.path, root))
    return {"garbled": sorted(garbled), "fragmented": sorted(fragmented), "engines": dict(engines)}


def doc_pair_counts(report: DedupReport) -> list[dict[str, object]]:
    counter: Counter[tuple[str, str, str, str]] = Counter()
    for group in report.exact_groups:
        docs = list(group.documents)
        for i in range(len(docs)):
            for j in range(i + 1, len(docs)):
                counter[(docs[i], docs[j], "exact", group.scope)] += 1
        if len(docs) == 1:
            counter[(docs[0], docs[0], "exact", group.scope)] += 1
    for pair in report.near_pairs + report.overlap_pairs:
        a, b = sorted((pair.left_doc, pair.right_doc))
        counter[(a, b, pair.kind, pair.scope)] += 1
    return [
        {"left_doc": a, "right_doc": b, "kind": k, "scope": s, "count": n}
        for (a, b, k, s), n in counter.most_common()
    ]


def simulate_update(root: Path, svc: KnowledgeLifecycleService, official: dict[tuple[str, str], Path]) -> dict:
    source = official.get((UPDATE_DOC, "fa"))
    if source is None:
        return {"status": "skipped", "reason": f"{UPDATE_DOC} (fa) not found"}
    result: dict[str, object] = {"document_id": UPDATE_DOC, "language": "fa", "source": rel(source, root)}
    # 1) unchanged file → no new version
    unchanged = svc.ingest(ingest_file(source, repo_root=root), effective_from=UPDATE_EFFECTIVE)
    result["reingest_unchanged"] = unchanged.action
    # 2) modified temp copy (same name under a temporary corpus/fa) → new version
    with tempfile.TemporaryDirectory(prefix="rag-phase5-") as tmp:
        target = Path(tmp) / "corpus" / "fa" / source.name
        target.parent.mkdir(parents=True)
        shutil.copy2(source, target)
        doc = Document(str(target))
        doc.add_paragraph(UPDATE_PARAGRAPH)
        doc.save(str(target))
        updated = ingest_file(target, repo_root=root)
        outcome = svc.ingest(updated, effective_from=UPDATE_EFFECTIVE)
    item = svc.repository.find_by_document(DocumentId(updated.document_id))
    assert item is not None
    fa = svc.language_of("fa")
    versions = item.versions_for(fa)
    result.update(
        {
            "action": outcome.action,
            "new_version": outcome.version,
            "supersedes_chain": [str(t) for t in item.supersedes_chain(fa)],
            "versions": [
                {
                    "version": str(v.tag),
                    "status": v.status.value,
                    "effective_from": v.effective_from.isoformat() if v.effective_from else None,
                    "effective_to": v.effective_to.isoformat() if v.effective_to else None,
                    "supersedes": str(v.supersedes) if v.supersedes else None,
                    "file_sha256": v.file_sha256[:16],
                    "chunks_active": v.count(ChunkStatus.ACTIVE),
                    "chunks_stale": v.count(ChunkStatus.STALE),
                    "chunks_retired": v.count(ChunkStatus.RETIRED),
                }
                for v in versions
            ],
            "en_version_untouched": str(item.active_version(svc.language_of("en")).tag),
            "events": [e.name for e in item.events],
        }
    )
    return result


def lifecycle_totals(svc: KnowledgeLifecycleService) -> dict[str, int]:
    totals: Counter[str] = Counter()
    for item in svc.items():
        totals["items"] += 1
        for v in item.versions:
            totals["versions"] += 1
            totals[f"versions_{v.status.value}"] += 1
            for status in ChunkStatus:
                totals[f"chunks_{status.value}"] += v.count(status)
        if len({v.language for v in item.versions}) == 2:
            totals["bilingual_items"] += 1
    for key in ("versions_draft", "versions_active", "versions_superseded", "versions_archived",
                "chunks_active", "chunks_stale", "chunks_retired"):
        totals.setdefault(key, 0)
    return dict(totals)


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 5 lifecycle + dedup over the corpus.")
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
    corpus = root / "corpus"
    out_dir = args.out or (root / "results" / "phase-05")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_json = out_dir / f"dedup-{stamp}.json"
    timings: dict[str, float] = {}
    failures: list[dict[str, str]] = []

    t = time.perf_counter()
    official_paths = collect(corpus, "fa") + collect(corpus, "en")
    derived_paths = collect(corpus, "derived")
    official: list[IngestedDocument] = []
    derived: list[IngestedDocument] = []
    for paths, bucket in ((official_paths, official), (derived_paths, derived)):
        for path in paths:
            try:
                bucket.append(ingest_file(path, repo_root=root))
            except Exception as exc:  # noqa: BLE001
                failures.append({"path": rel(path, root), "reason": str(exc), "error_type": type(exc).__name__})
    timings["ingest"] = time.perf_counter() - t

    t = time.perf_counter()
    svc = KnowledgeLifecycleService()
    actions: Counter[str] = Counter()
    by_key: dict[tuple[str, str], Path] = {}
    for doc in official:
        actions[svc.ingest(doc, effective_from=CORPUS_EFFECTIVE).action] += 1
        if doc.language is not None:
            by_key[(doc.document_id, doc.language.value)] = doc.path
    before = lifecycle_totals(svc)
    simulation = simulate_update(root, svc, by_key)
    after = lifecycle_totals(svc)
    timings["lifecycle"] = time.perf_counter() - t

    config = DedupConfig()
    finder = DuplicateFinder(config)
    chunk_records, doc_records = to_records(official + derived, root)
    t = time.perf_counter()
    chunk_report = finder.find(chunk_records)
    timings["dedup_chunks"] = time.perf_counter() - t
    doc_config = DedupConfig(shingle_mode="char", char_k=5, exhaustive=True, containment_threshold=0.80)
    t = time.perf_counter()
    doc_report = DuplicateFinder(doc_config).find(doc_records)
    timings["dedup_documents"] = time.perf_counter() - t
    timings["total"] = sum(timings.values())
    pdfq = pdf_quality(official + derived, failures, root)

    scope = chunk_report.count_by_scope()
    doc_scope = doc_report.count_by_scope()
    sim_ok = (
        simulation.get("action") == "new_version"
        and simulation.get("reingest_unchanged") == "unchanged"
        and any(v["status"] == VersionStatus.SUPERSEDED.value and v["chunks_retired"] > 0
                for v in simulation.get("versions", []))  # type: ignore[union-attr]
    )
    pytest_ok = args.pytest_exit in (None, "0", 0)
    status = "PASS" if (not failures and sim_ok and pytest_ok and chunk_report.bilingual_pairs_excluded >= 0) else "FAIL"

    payload = {
        "kit": KIT,
        "run_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": status,
        "files": {"official": len(official_paths), "derived": len(derived_paths), "failures": failures},
        "lifecycle": {
            "actions": dict(actions),
            "before_update": before,
            "after_update": after,
            "simulation": simulation,
        },
        "dedup_config": config.__dict__,
        "chunk_level": chunk_report.to_dict(),
        "chunk_level_document_pairs": doc_pair_counts(chunk_report),
        "document_level": doc_report.to_dict(),
        "doc_level_config": doc_config.__dict__,
        "pdf_text_quality": pdfq,
        "timings_s": {k: round(v, 3) for k, v in timings.items()},
        "pytest": {
            "passed": args.pytest_passed, "failed": args.pytest_failed, "errors": args.pytest_errors,
            "exit": args.pytest_exit, "result_line": args.pytest_line,
        },
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    sim_versions = simulation.get("versions", [])
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
    print(f"files_official: {len(official_paths)}")
    print(f"files_derived: {len(derived_paths)}")
    print(f"ingest_failures: {len(failures)}")
    print(f"knowledge_items: {after.get('items', 0)}")
    print(f"bilingual_items: {after.get('bilingual_items', 0)}")
    print(f"versions_total: {after.get('versions', 0)}")
    print(f"versions_active: {after['versions_active']}")
    print(f"versions_superseded: {after['versions_superseded']}")
    print(f"versions_draft: {after['versions_draft']}")
    print(f"versions_archived: {after['versions_archived']}")
    print(f"chunks_active: {after['chunks_active']}")
    print(f"chunks_stale: {after['chunks_stale']}")
    print(f"chunks_retired: {after['chunks_retired']}")
    print(f"update_doc: {UPDATE_DOC} fa")
    print(f"update_reingest_unchanged: {simulation.get('reingest_unchanged')}")
    print(f"update_action: {simulation.get('action')} -> {simulation.get('new_version')}")
    print(f"update_supersedes_chain: {' <- '.join(simulation.get('supersedes_chain', []))}")  # type: ignore[arg-type]
    for v in sim_versions:  # type: ignore[union-attr]
        print(
            f"update_version_{v['version']}: {v['status']} from={v['effective_from']} to={v['effective_to']} "
            f"active={v['chunks_active']} retired={v['chunks_retired']}"
        )
    print(f"dedup_records_chunks: {chunk_report.records}")
    print(f"exact_dup_groups: {len(chunk_report.exact_groups)} "
          f"(rendition {scope['exact_groups']['rendition']}, cross_document {scope['exact_groups']['cross_document']})")
    print(f"near_dup_pairs: {len(chunk_report.near_pairs)} "
          f"(rendition {scope['near_pairs']['rendition']}, cross_document {scope['near_pairs']['cross_document']})")
    print(f"overlap_pairs: {len(chunk_report.overlap_pairs)} "
          f"(rendition {scope['overlap_pairs']['rendition']}, cross_document {scope['overlap_pairs']['cross_document']})")
    print(f"bilingual_pairs_excluded: {chunk_report.bilingual_pairs_excluded} "
          f"(would-flag; candidates skipped {chunk_report.bilingual_candidates_seen})")
    print(f"lsh_candidates: {chunk_report.lsh_candidates}")
    recall = chunk_report.lsh_recall
    print(f"lsh_recall_vs_exact_jaccard: {'n/a' if recall is None else f'{recall:.3f}'}")
    print(f"doc_level_records: {doc_report.records}")
    print(f"doc_level_exact_groups: {len(doc_report.exact_groups)}")
    print(f"doc_level_near_pairs: {len(doc_report.near_pairs)} "
          f"(rendition {doc_scope['near_pairs']['rendition']}, cross_document {doc_scope['near_pairs']['cross_document']})")
    print(f"doc_level_overlap_pairs: {len(doc_report.overlap_pairs)} "
          f"(rendition {doc_scope['overlap_pairs']['rendition']}, cross_document {doc_scope['overlap_pairs']['cross_document']})")
    print(f"doc_level_bilingual_excluded: {doc_report.bilingual_pairs_excluded}")
    print(f"pdf_engines: {', '.join(f'{k}={v}' for k, v in sorted(pdfq['engines'].items())) or 'none'}")
    print(f"garbled_pdf_text: {len(pdfq['garbled'])} "
          f"({', '.join(Path(p).name for p in pdfq['garbled']) or 'none'})")
    print(f"fragmented_pdf_text: {len(pdfq['fragmented'])} "
          f"({', '.join(Path(p).name for p in pdfq['fragmented']) or 'none'})")
    print(f"doc_level_mode: char{doc_config.char_k} exhaustive near>={doc_config.near_threshold} "
          f"containment>={doc_config.containment_threshold}")
    print(f"chunk_thresholds: near_jaccard>={config.near_threshold} containment>={config.containment_threshold} "
          f"k={config.shingle_k} perms={config.num_perm} bands={config.bands} "
          f"min_exact_chars={config.min_exact_chars} min_shingles={config.min_shingles}")
    print("timings_s: " + " ".join(f"{k}={v:.2f}" for k, v in timings.items()))
    print(f"results_json: {out_json}")
    if failures:
        print("failures:")
        for f in failures:
            print(f"  - {f['path']}: {f['reason']}")
    print(SEPARATOR_END)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
