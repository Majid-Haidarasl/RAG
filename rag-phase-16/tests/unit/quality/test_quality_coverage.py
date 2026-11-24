"""Phase 15 coverage arithmetic: percentages, contexts, totals, least covered modules and the gate."""

import pytest

from rag_core.quality.domain.coverage import (
    CoverageReport,
    ModuleCoverage,
    context_of,
    coverage_gate,
    percent,
    totals,
)
from rag_core.shared_kernel.errors import InvariantError

pytestmark = [pytest.mark.quality]


def mod(
    path: str,
    statements: int,
    covered: int,
    branches: int = 0,
    covered_branches: int = 0,
) -> ModuleCoverage:
    return ModuleCoverage(path, statements, covered, branches, covered_branches)


def report(*mods: ModuleCoverage) -> CoverageReport:
    return CoverageReport(tuple(mods), branch_measured=True, tool="7.6.1")


def test_percent() -> None:
    assert percent(2, 3) == 66.7 and percent(5, 5) == 100.0 and percent(0, 4) == 0.0
    assert percent(0, 0) is None


@pytest.mark.parametrize(("part", "whole"), [(-1, 3), (1, -3), (4, 3)])
def test_percent_rejects(part: int, whole: int) -> None:
    with pytest.raises(InvariantError):
        percent(part, whole)


@pytest.mark.parametrize(
    ("path", "context"),
    [
        ("src/rag_core/qa/domain/answer.py", "qa"),
        ("src\\rag_core\\tuning\\application\\services.py", "tuning"),
        ("src/rag_core/__init__.py", "rag_core"),
        ("scripts/run_quality_check.py", "other"),
    ],
)
def test_context_of(path: str, context: str) -> None:
    assert context_of(path) == context


@pytest.mark.parametrize(
    ("statements", "covered", "branches", "covered_branches"),
    [(3, 4, 0, 0), (3, 3, 2, 3)],
)
def test_module_rejects_impossible_counts(
    statements: int, covered: int, branches: int, covered_branches: int
) -> None:
    with pytest.raises(InvariantError):
        mod("src/rag_core/x.py", statements, covered, branches, covered_branches)


def test_module_needs_a_path() -> None:
    with pytest.raises(InvariantError, match="path"):
        mod("  ", 1, 1)


def test_module_properties() -> None:
    m = mod("src/rag_core/qa/domain/answer.py", 40, 30, 10, 5)
    assert (m.context, m.line_pct, m.branch_pct, m.missed) == ("qa", 75.0, 50.0, 10)
    assert mod("src/rag_core/x.py", 0, 0).line_pct is None


def test_totals_and_contexts() -> None:
    r = report(
        mod("src/rag_core/qa/a.py", 10, 9, 4, 2),
        mod("src/rag_core/qa/b.py", 10, 7),
        mod("src/rag_core/rfp/c.py", 20, 20, 2, 2),
    )
    t = r.total
    assert (t.statements, t.covered, t.modules, t.line_pct, t.branch_pct) == (
        40,
        36,
        3,
        90.0,
        66.7,
    )
    ctx = r.by_context()
    assert (
        list(ctx) == ["qa", "rfp"]
        and ctx["qa"].line_pct == 80.0
        and ctx["rfp"].line_pct == 100.0
    )
    assert t.to_dict()["line_pct"] == 90.0 and totals([]).line_pct is None


def test_duplicate_module_rejected() -> None:
    with pytest.raises(InvariantError, match="twice"):
        report(mod("src/rag_core/a.py", 1, 1), mod("src/rag_core/a.py", 2, 2))


def test_lowest_sorts_by_pct_then_missed() -> None:
    r = report(
        mod("src/rag_core/a.py", 100, 50),
        mod("src/rag_core/b.py", 20, 10),
        mod("src/rag_core/c.py", 10, 0),
        mod("src/rag_core/d.py", 30, 30),
    )
    assert [m.path for m in r.lowest(n=2, min_statements=20)] == [
        "src/rag_core/a.py",
        "src/rag_core/b.py",
    ]
    assert [m.path for m in r.lowest(n=10, min_statements=0)][0] == "src/rag_core/c.py"
    with pytest.raises(InvariantError):
        r.lowest(n=-1)


def test_gate_pass_and_fail() -> None:
    good = report(mod("src/rag_core/qa/a.py", 100, 85))
    assert coverage_gate(good, 80).passed
    bad = coverage_gate(report(mod("src/rag_core/qa/a.py", 100, 79)), 80)
    assert (
        not bad.passed
        and bad.reasons == ("line 79.0<80",)
        and bad.to_dict()["line_pct"] == 79.0
    )


def test_gate_without_report_or_statements() -> None:
    assert coverage_gate(None, 80).reasons == ("no coverage report",)
    empty = coverage_gate(report(), 80)
    assert (
        not empty.passed
        and "modules 0<1" in empty.reasons
        and "no statements measured" in empty.reasons
    )


def test_gate_context_minimum() -> None:
    r = report(
        mod("src/rag_core/qa/a.py", 100, 95), mod("src/rag_core/rfp/b.py", 10, 5)
    )
    assert coverage_gate(r, 80).passed
    strict = coverage_gate(r, 80, min_context_pct=60)
    assert not strict.passed and strict.weak_contexts == ("rfp",)


@pytest.mark.parametrize(("line", "context"), [(101, 0), (80, 120)])
def test_gate_rejects_bad_thresholds(line: float, context: float) -> None:
    with pytest.raises(InvariantError, match="0..100"):
        coverage_gate(None, line, min_context_pct=context)
