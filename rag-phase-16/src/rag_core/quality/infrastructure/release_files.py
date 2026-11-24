"""File access for the release check: kit text files, versions in files, the .pptx zip."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path
import re
import tomllib
import zipfile

import yaml

SKIP_FOLDERS = frozenset({"__pycache__", "node_modules", "htmlcov"})
_PACKAGE_VERSION_RE = re.compile(
    r'^__version__\s*=\s*["\']([^"\']+)["\']', re.MULTILINE
)


def read_text(root: Path, rel: str) -> str | None:
    path = Path(root) / rel
    return path.read_text(encoding="utf-8") if path.is_file() else None


def _excluded(rel: str, exclude: Sequence[str]) -> bool:
    return any(
        rel == e.rstrip("/") or rel.startswith(e.rstrip("/") + "/") for e in exclude
    )


def kit_texts(
    root: Path, suffixes: Sequence[str], exclude: Sequence[str]
) -> Iterator[tuple[str, str]]:
    """(relative path, text) of every kit file with one of ``suffixes``; hidden folders are skipped."""
    root = Path(root)
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        rel = path.relative_to(root).as_posix()
        parts = Path(rel).parts[:-1]
        if any(
            p.startswith(".") or p.endswith(".egg-info") or p in SKIP_FOLDERS
            for p in parts
        ) or _excluded(rel, exclude):
            continue
        try:
            yield rel, path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue


def version_in(root: Path, rel: str, how: str) -> str | None:
    """``how``: ``pyproject`` (project.version), ``package`` (``__version__ = ...``) or ``yaml:<key>``."""
    text = read_text(root, rel)
    if text is None:
        return None
    if how == "pyproject":
        return str(tomllib.loads(text).get("project", {}).get("version") or "") or None
    if how == "package":
        m = _PACKAGE_VERSION_RE.search(text)
        return m.group(1) if m else None
    if how.startswith("yaml:"):
        data = yaml.safe_load(text) or {}
        value = data.get(how.split(":", 1)[1]) if isinstance(data, dict) else None
        return None if value is None else str(value)
    raise ValueError(f"unknown version source {how!r}")


def zip_names(path: Path) -> list[str] | None:
    """Names inside a zip file; ``None`` when it is missing or not a zip."""
    path = Path(path)
    if not path.is_file() or not zipfile.is_zipfile(path):
        return None
    with zipfile.ZipFile(path) as z:
        return z.namelist()


def evidence_matches(root: Path, pattern: str) -> list[str]:
    root = Path(root)
    return sorted(
        p.relative_to(root).as_posix() for p in root.glob(pattern) if p.is_file()
    )
