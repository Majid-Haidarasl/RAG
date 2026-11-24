"""Release checklist: every phase's planned deliverables and where they stand.

Statuses:

* ``done``     — delivered in this kit; every listed path must exist;
* ``external`` — delivered in its own repository folder (Phases 1–2 were
                 planning kits before the code base existed); not checked here;
* ``run``      — produced by running the kit (coverage report, results files);
                 the path is the output folder, it may be empty before a run;
* ``planned``  — scheduled for a later step (release tags, Phase 16).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from rag_core.shared_kernel.errors import InvariantError

STATUSES = ("done", "external", "run", "planned")


@dataclass(frozen=True)
class Deliverable:
    phase: int
    spec: str  # the deliverable as written in the phase plan
    status: str
    paths: tuple[str, ...] = ()  # where it lives in the kit (done / run)
    note: str = ""

    def __post_init__(self) -> None:
        if not 1 <= self.phase <= 99:
            raise InvariantError(f"phase must be 1..99, got {self.phase}")
        if not self.spec.strip():
            raise InvariantError(
                f"phase {self.phase}: a deliverable needs its spec text"
            )
        if self.status not in STATUSES:
            raise InvariantError(
                f"phase {self.phase} {self.spec!r}: status must be one of {', '.join(STATUSES)}"
            )
        if self.status == "done" and not self.paths:
            raise InvariantError(
                f"phase {self.phase} {self.spec!r}: a done deliverable needs its paths"
            )
        if self.status in ("external", "planned") and not self.note.strip():
            raise InvariantError(
                f"phase {self.phase} {self.spec!r}: {self.status} needs a note"
            )
        for p in self.paths:
            if p.startswith("/") or ".." in p.split("/"):
                raise InvariantError(
                    f"phase {self.phase}: path {p!r} must be relative to the kit root"
                )


@dataclass(frozen=True)
class ChecklistProblem:
    phase: int
    spec: str
    code: str
    detail: str = ""

    def __str__(self) -> str:
        return f"P{self.phase}:{self.code}:{self.spec}" + (
            f":{self.detail}" if self.detail else ""
        )


def checklist_problems(
    items: Sequence[Deliverable],
    exists: Callable[[str], bool],
    *,
    phases: Iterable[int] = range(1, 17),
) -> list[ChecklistProblem]:
    """Missing paths of done deliverables, phases without any deliverable, duplicate specs."""
    out: list[ChecklistProblem] = []
    seen: set[tuple[int, str]] = set()
    for d in items:
        key = (d.phase, d.spec.strip())
        if key in seen:
            out.append(ChecklistProblem(d.phase, d.spec, "duplicate"))
        seen.add(key)
        if d.status == "done":
            for p in d.paths:
                if not exists(p):
                    out.append(ChecklistProblem(d.phase, d.spec, "missing_path", p))
    have = {d.phase for d in items}
    for ph in phases:
        if ph not in have:
            out.append(ChecklistProblem(ph, "-", "phase_missing"))
    return out


def status_counts(items: Iterable[Deliverable]) -> dict[str, int]:
    counts = dict.fromkeys(STATUSES, 0)
    for d in items:
        counts[d.status] += 1
    return counts


def by_phase(items: Iterable[Deliverable]) -> dict[int, list[Deliverable]]:
    out: dict[int, list[Deliverable]] = {}
    for d in items:
        out.setdefault(d.phase, []).append(d)
    return dict(sorted(out.items()))


def phase_status(items: Sequence[Deliverable]) -> str:
    """One word per phase: ``done`` (all done/run), ``external``, ``planned`` (nothing delivered yet) or ``partial``."""
    if not items:
        return "missing"
    statuses = {d.status for d in items}
    if statuses <= {"done", "run"}:
        return "done"
    if statuses == {"external"}:
        return "external"
    if statuses == {"planned"}:
        return "planned"
    return "partial"
