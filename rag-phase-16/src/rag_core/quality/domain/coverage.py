"""Line and branch coverage per module, per bounded context and in total.

Numbers come from coverage.py (``coverage json``) through the infrastructure
reader; this module only does arithmetic. A module path is mapped to its
bounded context by the first folder below ``rag_core`` (``src/rag_core/qa/...``
-> ``qa``); files directly in ``rag_core`` count as ``rag_core``.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from rag_core.shared_kernel.errors import InvariantError


def percent(part: int, whole: int) -> float | None:
    """``part / whole`` in percent with one decimal; ``None`` when nothing was measured."""
    if part < 0 or whole < 0:
        raise InvariantError("coverage counts must be >= 0")
    if part > whole:
        raise InvariantError(f"covered {part} > total {whole}")
    if whole == 0:
        return None
    return round(100.0 * part / whole, 1)


def context_of(path: str) -> str:
    parts = [p for p in path.replace("\\", "/").split("/") if p]
    if "rag_core" not in parts:
        return "other"
    rest = parts[parts.index("rag_core") + 1:]
    if len(rest) <= 1:
        return "rag_core"
    return rest[0]


@dataclass(frozen=True)
class ModuleCoverage:
    path: str
    statements: int
    covered: int
    branches: int = 0
    covered_branches: int = 0
    missing_lines: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if not self.path.strip():
            raise InvariantError("a module needs a path")
        if not 0 <= self.covered <= self.statements:
            raise InvariantError(f"{self.path}: covered lines {self.covered} outside 0..{self.statements}")
        if not 0 <= self.covered_branches <= self.branches:
            raise InvariantError(f"{self.path}: covered branches {self.covered_branches} outside 0..{self.branches}")

    @property
    def context(self) -> str:
        return context_of(self.path)

    @property
    def line_pct(self) -> float | None:
        return percent(self.covered, self.statements)

    @property
    def branch_pct(self) -> float | None:
        return percent(self.covered_branches, self.branches)

    @property
    def missed(self) -> int:
        return self.statements - self.covered


@dataclass(frozen=True)
class CoverageTotals:
    statements: int
    covered: int
    branches: int = 0
    covered_branches: int = 0
    modules: int = 0

    @property
    def line_pct(self) -> float | None:
        return percent(self.covered, self.statements)

    @property
    def branch_pct(self) -> float | None:
        return percent(self.covered_branches, self.branches)

    def to_dict(self) -> dict[str, object]:
        return {"modules": self.modules, "statements": self.statements, "covered": self.covered,
                "line_pct": self.line_pct, "branches": self.branches, "covered_branches": self.covered_branches,
                "branch_pct": self.branch_pct}


def totals(modules: Iterable[ModuleCoverage]) -> CoverageTotals:
    mods = list(modules)
    return CoverageTotals(sum(m.statements for m in mods), sum(m.covered for m in mods),
                          sum(m.branches for m in mods), sum(m.covered_branches for m in mods), len(mods))


@dataclass(frozen=True)
class CoverageReport:
    modules: tuple[ModuleCoverage, ...]
    branch_measured: bool = False
    tool: str = ""

    def __post_init__(self) -> None:
        paths = [m.path for m in self.modules]
        if len(paths) != len(set(paths)):
            raise InvariantError("a module appears twice in the coverage report")

    @property
    def total(self) -> CoverageTotals:
        return totals(self.modules)

    def by_context(self) -> dict[str, CoverageTotals]:
        groups: dict[str, list[ModuleCoverage]] = {}
        for m in self.modules:
            groups.setdefault(m.context, []).append(m)
        return {k: totals(v) for k, v in sorted(groups.items())}

    def lowest(self, n: int = 10, min_statements: int = 20) -> list[ModuleCoverage]:
        """The ``n`` least covered modules with at least ``min_statements`` statements (most missed lines first on ties)."""
        if n < 0 or min_statements < 0:
            raise InvariantError("n and min_statements must be >= 0")
        big = [m for m in self.modules if m.statements >= min_statements and m.line_pct is not None]
        return sorted(big, key=lambda m: (m.line_pct, -m.missed, m.path))[:n]


@dataclass(frozen=True)
class GateResult:
    passed: bool
    line_pct: float | None
    min_line_pct: float
    reasons: tuple[str, ...] = ()
    weak_contexts: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {"passed": self.passed, "line_pct": self.line_pct, "min_line_pct": self.min_line_pct,
                "reasons": list(self.reasons), "weak_contexts": list(self.weak_contexts)}


def coverage_gate(report: CoverageReport | None, min_line_pct: float, *, min_context_pct: float = 0.0,
                  min_modules: int = 1) -> GateResult:
    """Pass when total line coverage >= ``min_line_pct``; contexts under ``min_context_pct`` are reported
    (and fail the gate only when ``min_context_pct`` > 0)."""
    if not 0 <= min_line_pct <= 100 or not 0 <= min_context_pct <= 100:
        raise InvariantError("coverage thresholds must be within 0..100")
    if report is None:
        return GateResult(False, None, min_line_pct, ("no coverage report",))
    reasons: list[str] = []
    total = report.total
    if total.modules < min_modules:
        reasons.append(f"modules {total.modules}<{min_modules}")
    pct = total.line_pct
    if pct is None:
        reasons.append("no statements measured")
    elif pct < min_line_pct:
        reasons.append(f"line {pct}<{min_line_pct}")
    weak: list[str] = []
    if min_context_pct > 0:
        for ctx, t in report.by_context().items():
            if t.line_pct is not None and t.line_pct < min_context_pct:
                weak.append(ctx)
        if weak:
            reasons.append(f"contexts below {min_context_pct}: {', '.join(weak)}")
    return GateResult(not reasons, pct, min_line_pct, tuple(reasons), tuple(weak))

