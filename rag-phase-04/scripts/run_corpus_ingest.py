#!/usr/bin/env python3
"""Ingest the ArmanRayan corpus (DOCX plus any derived DOC/PDF) and print a summary."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import sys

# Allow running without installation when needed.
ROOT_CANDIDATE = Path(__file__).resolve().parents[1]
src = ROOT_CANDIDATE / "src"
if src.is_dir() and str(src) not in sys.path:
    sys.path.insert(0, str(src))

from rag_core.ingestion.application.pipeline import ingest_file  # noqa: E402
from rag_core.ingestion.domain.catalog import PERSIAN_DIGIT_ID_DOCUMENTS  # noqa: E402
from rag_core.ingestion.domain.errors import IngestionError  # noqa: E402
from rag_core.ingestion.domain.model import IngestedDocument  # noqa: E402


FORMATS = (".docx", ".doc", ".pdf")
SEPARATOR_START = "======== PHASE 4 SUMMARY (paste this block) ========"
SEPARATOR_END = "======== END PHASE 4 SUMMARY ========"


def find_root(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.resolve()
    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents, ROOT_CANDIDATE]:
        if (candidate / "pyproject.toml").is_file() and (candidate / "corpus").is_dir():
            return candidate
    raise SystemExit("could not find the repo root (pyproject.toml + corpus/)")


def collect_files(corpus: Path) -> list[Path]:
    files: list[Path] = []
    for folder in (corpus / "fa", corpus / "en", corpus / "derived"):
        if not folder.exists():
            continue
        for path in sorted(folder.rglob("*")):
            if path.is_file() and path.suffix.lower() in FORMATS:
                files.append(path)
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest the ArmanRayan corpus.")
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
    files = collect_files(corpus)
    out_dir = args.out or (root / "results" / "phase-04")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_json = out_dir / f"ingest-{stamp}.json"

    by_format: Counter[str] = Counter()
    success: list[dict] = []
    failures: list[dict] = []
    chunks_total = 0
    scanned_docs = 0
    scanned_pages_total = 0
    norm = Counter()
    id_fix_docs: list[str] = []

    for path in files:
        suffix = path.suffix.lower().lstrip(".")
        by_format[suffix] += 1
        try:
            doc = ingest_file(path, repo_root=root)
        except Exception as exc:  # noqa: BLE001
            failures.append(
                {
                    "path": str(path.relative_to(root) if path.is_relative_to(root) else path),
                    "format": suffix,
                    "reason": str(exc),
                    "error_type": type(exc).__name__,
                }
            )
            continue
        assert isinstance(doc, IngestedDocument)
        chunks_total += len(doc.chunks)
        if doc.is_scanned:
            scanned_docs += 1
            scanned_pages_total += len(doc.scanned_pages)
        for key in ("yeh_kaf", "zwnj", "id_digits", "arabic_indic"):
            norm[key] += getattr(doc.normalization, key)
        if doc.normalization.id_digits:
            id_fix_docs.append(doc.document_id)
        rel = str(path.relative_to(root) if path.is_relative_to(root) else path)
        success.append(
            {
                **doc.to_summary(),
                "path": rel,
                "metadata": doc.metadata,
            }
        )

    payload = {
        "kit": "rag-core 0.4.0 (phase 4)",
        "ingested_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "corpus": str(corpus),
        "files_found": len(files),
        "by_format": dict(by_format),
        "success": len(success),
        "fail": len(failures),
        "chunks_total": chunks_total,
        "scanned_docs": scanned_docs,
        "scanned_pages": scanned_pages_total,
        "normalization": dict(norm),
        "id_digit_fixes_documents": sorted(set(id_fix_docs)),
        "expected_persian_digit_id_docs": sorted(PERSIAN_DIGIT_ID_DOCUMENTS),
        "failures": failures,
        "documents": success,
        "pytest": {
            "passed": args.pytest_passed,
            "failed": args.pytest_failed,
            "errors": args.pytest_errors,
            "exit": args.pytest_exit,
            "result_line": args.pytest_line,
        },
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    pytest_ok = args.pytest_exit in (None, "0", 0)
    status = "PASS" if (not failures and success and pytest_ok) else "FAIL"
    print()
    print(SEPARATOR_START)
    print(f"status: {status}")
    print("kit: rag-core 0.4.0 (phase 4)")
    if args.python_version:
        print(f"python: {args.python_version}")
    if args.pytest_exit is not None:
        print(f"pytest_exit: {args.pytest_exit}")
        print(f"pytest_passed: {args.pytest_passed or 0}")
        print(f"pytest_failed: {args.pytest_failed or 0}")
        print(f"pytest_errors: {args.pytest_errors or 0}")
        if args.pytest_line:
            print(f"pytest_line: {args.pytest_line}")
    print(f"files_found: {len(files)}")
    print(f"by_format_docx: {by_format.get('docx', 0)}")
    print(f"by_format_doc: {by_format.get('doc', 0)}")
    print(f"by_format_pdf: {by_format.get('pdf', 0)}")
    print(f"success: {len(success)}")
    print(f"fail: {len(failures)}")
    print(f"chunks_total: {chunks_total}")
    print(f"scanned_docs: {scanned_docs}")
    print(f"scanned_pages: {scanned_pages_total}")
    print(f"normalization_yeh_kaf: {norm.get('yeh_kaf', 0)}")
    print(f"normalization_zwnj: {norm.get('zwnj', 0)}")
    print(f"normalization_id_digits: {norm.get('id_digits', 0)}")
    print(f"normalization_arabic_indic: {norm.get('arabic_indic', 0)}")
    print(f"id_digit_fix_docs: {','.join(sorted(set(id_fix_docs))) or '(none)'}")
    print(f"results_json: {out_json}")
    if failures:
        print("failures:")
        for item in failures:
            print(f"  - {item['path']}: {item['reason']}")
    print(SEPARATOR_END)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
