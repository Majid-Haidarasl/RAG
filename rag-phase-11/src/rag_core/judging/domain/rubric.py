"""Judge rubric (Phase 10): five criteria scored to a 20-point total.

A rubric is a list of criteria. Each criterion has a maximum, a minimum that
must be reached for acceptance, aliases the parser accepts for its key
(``groundedness`` → ``grounding``), and one guidance line per output kind.
The points of all criteria add up to ``out_of`` (20); ``accept_total`` is the
initial acceptance bar of the project plan (18/20).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import re

from rag_core.judging.domain.model import JudgeThreshold
from rag_core.shared_kernel.errors import InvariantError

_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,40}$")


class OutputKind(StrEnum):
    """What is being judged. The kind selects guidance lines and the prompt."""

    QA_ANSWER = "qa_answer"      # a node-scoped answer was expected (Phase 8)
    QA_REFUSAL = "qa_refusal"    # a refusal / escalation was expected (Phase 8)
    IKE_SUMMARY = "ike_summary"  # an issue summary built from IKE facts (Phase 9)


def canonical_name(name: str) -> str:
    """``"Citation Quality"`` → ``"citation_quality"`` (lower case, ``_`` separators)."""
    return re.sub(r"[\s\-]+", "_", str(name).strip().lower())


@dataclass(frozen=True)
class Criterion:
    key: str
    max_points: int
    min_points: int
    title_en: str = ""
    title_fa: str = ""
    aliases: tuple[str, ...] = ()
    guidance: tuple[tuple[str, str], ...] = ()  # (kind, text)

    def __post_init__(self) -> None:
        if not _KEY_RE.match(self.key):
            raise InvariantError(f"invalid criterion key {self.key!r}")
        if self.max_points <= 0:
            raise InvariantError(f"{self.key}: max_points must be positive")
        if not 0 <= self.min_points <= self.max_points:
            raise InvariantError(f"{self.key}: min_points must be within 0..{self.max_points}")

    @property
    def names(self) -> tuple[str, ...]:
        return (self.key, *(canonical_name(a) for a in self.aliases))

    def guidance_for(self, kind: str) -> str:
        for k, text in self.guidance:
            if k == str(kind):
                return text
        return ""


@dataclass(frozen=True)
class Rubric:
    rubric_id: str
    version: str
    criteria: tuple[Criterion, ...]
    out_of: int = 20
    accept_total: int = 18
    _lookup: dict[str, str] = field(default_factory=dict, init=False, repr=False, compare=False, hash=False)

    def __post_init__(self) -> None:
        if not self.rubric_id.strip() or not self.version.strip():
            raise InvariantError("rubric id and version are required")
        if not self.criteria:
            raise InvariantError("a rubric needs at least one criterion")
        keys = [c.key for c in self.criteria]
        if len(keys) != len(set(keys)):
            raise InvariantError("duplicate criterion keys")
        total = sum(c.max_points for c in self.criteria)
        if total != self.out_of:
            raise InvariantError(f"criteria add up to {total}, expected {self.out_of}")
        if not 0 < self.accept_total <= self.out_of:
            raise InvariantError(f"accept_total must be within 1..{self.out_of}")
        lookup: dict[str, str] = {}
        for c in self.criteria:
            for name in c.names:
                if name in lookup and lookup[name] != c.key:
                    raise InvariantError(f"name {name!r} is used by {lookup[name]} and {c.key}")
                lookup[name] = c.key
        self._lookup.update(lookup)

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(c.key for c in self.criteria)

    @property
    def threshold(self) -> JudgeThreshold:
        return JudgeThreshold(self.accept_total, self.out_of)

    @property
    def minimums(self) -> dict[str, int]:
        return {c.key: c.min_points for c in self.criteria}

    @property
    def maximums(self) -> dict[str, int]:
        return {c.key: c.max_points for c in self.criteria}

    @property
    def label(self) -> str:
        return f"{self.rubric_id}@{self.version}"

    def criterion(self, key: str) -> Criterion:
        for c in self.criteria:
            if c.key == key:
                return c
        raise InvariantError(f"unknown criterion {key!r}")

    def resolve(self, name: str) -> str | None:
        """Canonical criterion key for a key or alias written by a judge, else ``None``."""
        return self._lookup.get(canonical_name(name))

    def guidance_lines(self, kind: str) -> list[str]:
        return [f"- {c.key} (0-{c.max_points}): {c.guidance_for(kind) or c.title_en}" for c in self.criteria]

    def reply_skeleton(self) -> str:
        inner = ", ".join(f'"{c.key}": <0-{c.max_points}>' for c in self.criteria)
        return '{"scores": {' + inner + '}, "issues": ["<short problem>", "..."]}'

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.rubric_id, "version": self.version, "out_of": self.out_of, "accept_total": self.accept_total,
            "criteria": [{"key": c.key, "max": c.max_points, "min": c.min_points, "title_en": c.title_en,
                          "title_fa": c.title_fa} for c in self.criteria],
        }


def default_rubric() -> Rubric:
    """Same criteria and points as ``config/prompts/judge/rubric.yaml`` (guidance kept short here)."""
    return Rubric(
        "judge.rubric",
        "1.0.0",
        (
            Criterion("grounding", 5, 4, "Grounding", "پشتوانه‌داری",
                      ("groundedness", "faithfulness", "grounded", "support", "evidence")),
            Criterion("correctness", 5, 4, "Correctness", "درستی",
                      ("accuracy", "correct", "factual_accuracy", "factuality")),
            Criterion("citation", 4, 3, "Citation / traceability", "ارجاع",
                      ("citations", "traceability", "references", "attribution", "cite")),
            Criterion("completeness", 3, 2, "Completeness", "کامل‌بودن", ("coverage", "complete")),
            Criterion("clarity", 3, 2, "Language and clarity", "زبان و وضوح",
                      ("language", "clarity_language", "language_clarity", "fluency", "style")),
        ),
        out_of=20,
        accept_total=18,
    )
