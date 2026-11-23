"""Phase 15 readers: ``coverage json`` files and the static test inventory."""

import json
from pathlib import Path

import pytest

from rag_core.quality.infrastructure.coverage_json import load_coverage_report, module_from_entry, report_from_dict
from rag_core.quality.infrastructure.inventory import count_test_functions, inventory
from rag_core.shared_kernel.errors import InvariantError

pytestmark = [pytest.mark.quality]

SAMPLE = {
    "meta": {"version": "7.6.1", "branch_coverage": True},
    "files": {
        "src/rag_core/qa/domain/answer.py": {"summary": {"num_statements": 40, "covered_lines": 36,
                                                         "num_branches": 10, "covered_branches": 8},
                                             "missing_lines": [5, 9]},
        "src\\rag_core\\__init__.py": {"summary": {"num_statements": 2, "covered_lines": 2}},
        "tests/unit/qa/test_x.py": {"summary": {"num_statements": 10, "covered_lines": 10}},
        "scripts/run_quality_check.py": {"summary": {"num_statements": 300, "covered_lines": 0}},
    },
}


def test_report_keeps_package_modules_only() -> None:
    r = report_from_dict(SAMPLE)
    # sorted by the raw key: "src/" sorts before "src\\"
    assert [m.path for m in r.modules] == ["src/rag_core/qa/domain/answer.py", "src/rag_core/__init__.py"]
    assert r.branch_measured and r.tool == "7.6.1"
    assert (r.total.statements, r.total.covered, r.total.branches) == (42, 38, 10)
    assert r.modules[0].missing_lines == (5, 9)


def test_report_without_meta() -> None:
    r = report_from_dict({"files": {"rag_core/a.py": {"summary": {"num_statements": 1, "covered_lines": 0}}}})
    assert not r.branch_measured and r.tool == "" and r.total.line_pct == 0.0


@pytest.mark.parametrize("data", [[], {"files": []}])
def test_report_needs_files_mapping(data: object) -> None:
    with pytest.raises(InvariantError, match="files"):
        report_from_dict(data)


@pytest.mark.parametrize("entry", [None, {"summary": {"covered_lines": 1}},
                                   {"summary": {"num_statements": True, "covered_lines": 1}}])
def test_bad_entries(entry: object) -> None:
    with pytest.raises(InvariantError):
        module_from_entry("src/rag_core/a.py", entry)


def test_load_missing_and_present(tmp_path: Path) -> None:
    assert load_coverage_report(tmp_path / "none.json") is None
    path = tmp_path / "coverage.json"
    path.write_text(json.dumps(SAMPLE), encoding="utf-8")
    assert load_coverage_report(path).total.modules == 2


def test_count_test_functions() -> None:
    source = (
        "import pytest\n"
        "def helper():\n    pass\n"
        "def test_a():\n    pass\n"
        "@pytest.mark.parametrize('x', [1, 2])\n"
        "def test_b(x):\n    pass\n"
        "class TestGroup:\n    def test_c(self):\n        pass\n"
        "async def test_d():\n    pass\n"
    )
    assert count_test_functions(source) == (4, 1)


def test_inventory_per_folder(tmp_path: Path) -> None:
    (tmp_path / "qa").mkdir()
    (tmp_path / "qa" / "test_one.py").write_text("def test_a():\n    pass\n\ndef test_b():\n    pass\n",
                                                 encoding="utf-8")
    (tmp_path / "qa" / "helpers.py").write_text("def test_not_collected():\n    pass\n", encoding="utf-8")
    (tmp_path / "test_top.py").write_text("def test_c():\n    pass\n", encoding="utf-8")
    rows = {r.folder: r for r in inventory(tmp_path)}
    assert set(rows) == {".", "qa"}
    assert (rows["qa"].files, rows["qa"].functions, rows["qa"].parametrized) == (1, 2, 0)
    assert rows["."].functions == 1
