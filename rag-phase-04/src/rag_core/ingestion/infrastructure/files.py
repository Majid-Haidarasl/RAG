"""Local file helpers. No network."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re

from rag_core.shared_kernel.numerals import normalize_digits


_DOC_ID_IN_NAME = re.compile(
    r"(AR-[A-Z]{2,5}-[0-9\u06F0-\u06F9\u0660-\u0669]{3})",
    re.IGNORECASE,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def document_id_from_name(path: Path) -> str:
    match = _DOC_ID_IN_NAME.search(path.name)
    if not match:
        return normalize_digits(path.stem.split("-")[0] if path.stem else path.name)
    return normalize_digits(match.group(1).upper())


def language_from_path(path: Path) -> str | None:
    parts = {p.lower() for p in path.parts}
    if "fa" in parts:
        return "fa"
    if "en" in parts:
        return "en"
    name = path.name.lower()
    if name.endswith("-fa.docx") or ".fa." in name:
        return "fa"
    if name.endswith("-en.docx") or ".en." in name:
        return "en"
    return None
