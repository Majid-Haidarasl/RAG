"""Release check (Phase 16): versions agree, documents are complete, no chat-style text is left.

Everything here works on strings and numbers handed in by the infrastructure
layer; nothing reads files.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from rag_core.shared_kernel.errors import InvariantError

_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
# "## [1.0.0] — 1405-09-03" or "## 0.15.0"
_CHANGELOG_HEADING_RE = re.compile(r"^##\s+\[?(\d+\.\d+\.\d+)\]?", re.MULTILINE)


def require_version(value: str, where: str) -> str:
    if not _VERSION_RE.match(value or ""):
        raise InvariantError(f"{where}: version must look like 1.0.0, got {value!r}")
    return value


# ---- versions ---------------------------------------------------------------------------------


def version_problems(expected: str, found: Mapping[str, str | None]) -> list[str]:
    """``where=found`` for every place whose version differs from ``expected`` (missing counts too)."""
    require_version(expected, "expected")
    return [
        f"{where}={value or '-'}" for where, value in found.items() if value != expected
    ]


# ---- phrases ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class PhraseHit:
    path: str
    line: int
    phrase: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}:{self.phrase}"


def find_phrases(text: str, phrases: Sequence[str]) -> list[tuple[int, str]]:
    """(line number, phrase) for every phrase found, case-insensitive; one hit per phrase and line."""
    wanted = [p.lower() for p in phrases if p.strip()]
    hits: list[tuple[int, str]] = []
    for number, line in enumerate((text or "").splitlines(), 1):
        low = line.lower()
        hits.extend((number, p) for p in wanted if p in low)
    return hits


def scan_texts(
    texts: Iterable[tuple[str, str]], phrases: Sequence[str]
) -> list[PhraseHit]:
    """``texts`` is (path, content); returns every hit in path order."""
    if not [p for p in phrases if p.strip()]:
        raise InvariantError("the phrase scan needs at least one phrase")
    out: list[PhraseHit] = []
    for path, text in texts:
        out.extend(PhraseHit(path, n, p) for n, p in find_phrases(text, phrases))
    return out


# ---- documents --------------------------------------------------------------------------------


@dataclass(frozen=True)
class DocRequirement:
    path: str
    min_chars: int = 400
    markers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (
            not self.path.strip()
            or self.path.startswith("/")
            or ".." in self.path.split("/")
        ):
            raise InvariantError(
                f"document path {self.path!r} must be relative to the kit root"
            )
        if self.min_chars < 0:
            raise InvariantError(f"{self.path}: min_chars must be >= 0")


@dataclass(frozen=True)
class DocCheck:
    path: str
    exists: bool
    chars: int = 0
    min_chars: int = 0
    missing_markers: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.exists and self.chars >= self.min_chars and not self.missing_markers

    @property
    def reason(self) -> str:
        if not self.exists:
            return "missing"
        if self.chars < self.min_chars:
            return f"short:{self.chars}<{self.min_chars}"
        if self.missing_markers:
            return "markers:" + "|".join(self.missing_markers)
        return "ok"


def check_doc(req: DocRequirement, text: str | None) -> DocCheck:
    """``text`` is ``None`` when the file does not exist."""
    if text is None:
        return DocCheck(req.path, False, 0, req.min_chars, req.markers)
    chars = len(text.strip())
    missing = tuple(m for m in req.markers if m not in text)
    return DocCheck(req.path, True, chars, req.min_chars, missing)


# ---- changelog --------------------------------------------------------------------------------


def changelog_versions(text: str) -> list[str]:
    """Version headings in file order."""
    return _CHANGELOG_HEADING_RE.findall(text or "")


def changelog_problems(text: str, required: Sequence[str], newest: str) -> list[str]:
    found = changelog_versions(text)
    problems = [f"missing:{v}" for v in required if v not in found]
    if not found:
        problems.append("no_versions")
    elif found[0] != newest:
        problems.append(f"newest:{found[0]}!={newest}")
    dupes = sorted({v for v in found if found.count(v) > 1})
    problems += [f"duplicate:{v}" for v in dupes]
    return problems


# ---- presentation -----------------------------------------------------------------------------

_SLIDE_RE = re.compile(r"^ppt/slides/slide(\d+)\.xml$")


def slide_count(names: Iterable[str]) -> int:
    """Slides in a .pptx, from the names inside the zip."""
    return sum(1 for n in names if _SLIDE_RE.match(n))


def presentation_problems(
    names: Sequence[str] | None, min_slides: int, max_slides: int
) -> list[str]:
    if min_slides < 1 or max_slides < min_slides:
        raise InvariantError("slide limits must satisfy 1 <= min <= max")
    if names is None:
        return ["missing"]
    if "[Content_Types].xml" not in names or "ppt/presentation.xml" not in names:
        return ["not_a_pptx"]
    n = slide_count(names)
    return (
        []
        if min_slides <= n <= max_slides
        else [f"slides:{n} outside {min_slides}..{max_slides}"]
    )
