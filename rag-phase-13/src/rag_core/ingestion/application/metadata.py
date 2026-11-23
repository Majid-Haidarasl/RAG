"""Build and validate knowledge metadata records against the Phase 4 JSON Schema."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from rag_core.ingestion.domain.catalog import lookup
from rag_core.shared_kernel.language import LanguageCode

SCHEMA_RELATIVE = Path("schemas/knowledge-metadata.json")


def find_repo_root(start: Path | None = None) -> Path:
    cur = (start or Path.cwd()).resolve()
    for candidate in [cur, *cur.parents]:
        if (candidate / "pyproject.toml").is_file() and (candidate / SCHEMA_RELATIVE).is_file():
            return candidate
    raise FileNotFoundError(f"cannot locate {SCHEMA_RELATIVE} upward from {cur}")


def schema_path(repo_root: Path | None = None) -> Path:
    root = repo_root if repo_root is not None else find_repo_root()
    return root / SCHEMA_RELATIVE


def load_schema(repo_root: Path | None = None) -> dict:
    path = schema_path(repo_root)
    return json.loads(path.read_text(encoding="utf-8"))


def validate_metadata(record: dict, repo_root: Path | None = None) -> None:
    import jsonschema

    jsonschema.validate(instance=record, schema=load_schema(repo_root))


def bilingual_pair_name(path: Path, language: LanguageCode | None) -> str | None:
    """Best-effort sibling file name in the other language folder."""
    if language is None:
        return None
    parent = path.parent
    if parent.name == "fa":
        other = parent.parent / "en"
        target_lang = "en"
    elif parent.name == "en":
        other = parent.parent / "fa"
        target_lang = "fa"
    else:
        return None
    if not other.is_dir():
        return None
    prefix = path.name.split("-")[0] + "-" + path.name.split("-")[1] if path.name.count("-") >= 1 else path.stem
    # IDs are AR-XXX-NNN
    parts = path.name.split("-")
    if len(parts) >= 3:
        prefix = "-".join(parts[:3])
    for candidate in other.iterdir():
        if candidate.name.startswith(prefix):
            return candidate.name
    return None


def build_metadata(
    *,
    document_id: str,
    path: Path,
    language: LanguageCode | None,
    file_sha256: str,
    byte_size: int,
    file_format: str,
    page_count: int,
    is_scanned: bool,
    chunk_count: int,
    char_count: int,
    repo_root: Path | None = None,
) -> dict:
    entry = lookup(document_id)
    pair = bilingual_pair_name(path, language)
    other_lang = None
    if language is not None:
        other_lang = "en" if language is LanguageCode.FA else "fa"
    record = {
        "id": document_id,
        "language": None if language is None else language.value,
        "owning_node": entry.owning_node if entry else None,
        "additional_nodes": list(entry.additional_nodes) if entry else [],
        "doc_type": entry.doc_type if entry else "unknown",
        "title_fa": entry.title_fa if entry else None,
        "title_en": entry.title_en if entry else None,
        "version": entry.version if entry else "1.0",
        "version_status": entry.version_status if entry else "Approved",
        "date_jalali": entry.date_jalali if entry else None,
        "date_gregorian": entry.date_gregorian if entry else None,
        "confidentiality": entry.confidentiality if entry else "internal",
        "file_name": path.name,
        "source_path": str(path),
        "file_format": file_format,
        "file_sha256": file_sha256,
        "byte_size": byte_size,
        "page_count": page_count or None,
        "char_count": char_count,
        "chunk_count": chunk_count,
        "is_scanned": is_scanned,
        "bilingual_pair": None
        if not pair
        else {"language": other_lang, "file_name": pair},
        "ingested_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    # Drop null optional fields that the schema marks as optional? Keep them;
    # schema will use type ["string", "null"] where needed.
    validate_metadata(record, repo_root=repo_root)
    return record
