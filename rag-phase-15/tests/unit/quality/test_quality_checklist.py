"""Phase 15 release checklist: deliverable rules, problems, phase status and the shipped checklist."""

from pathlib import Path

import pytest

from rag_core.quality.domain.checklist import (
    ChecklistProblem,
    Deliverable,
    by_phase,
    checklist_problems,
    phase_status,
    status_counts,
)
from rag_core.quality.infrastructure.checklist_yaml import (
    deliverables_from_dict,
    load_deliverables,
)
from rag_core.quality.infrastructure.config import load_quality_settings
from rag_core.shared_kernel.errors import InvariantError

pytestmark = [pytest.mark.quality]

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"phase": 1, "spec": " ", "status": "done", "paths": ("a",)},
        {"phase": 1, "spec": "x", "status": "done"},
        {"phase": 1, "spec": "x", "status": "planned"},
        {"phase": 1, "spec": "x", "status": "done", "paths": ("/etc/x",)},
        {"phase": 1, "spec": "x", "status": "done", "paths": ("docs/../../x",)},
    ],
)
def test_deliverable_rules(kwargs: dict) -> None:
    with pytest.raises(InvariantError):
        Deliverable(**kwargs)


def test_problems_missing_path_duplicate_and_phase() -> None:
    items = [
        Deliverable(1, "plan", "done", ("docs/a.md",)),
        Deliverable(1, "plan", "external", note="repo"),
        Deliverable(3, "code", "done", ("src/x.py",)),
    ]
    problems = checklist_problems(items, lambda p: p == "src/x.py", phases=range(1, 4))
    assert [str(p) for p in problems] == [
        "P1:missing_path:plan:docs/a.md",
        "P1:duplicate:plan",
        "P2:phase_missing:-",
    ]
    assert str(ChecklistProblem(4, "s", "c")) == "P4:c:s"


def test_counts_and_phase_status() -> None:
    items = [
        Deliverable(1, "a", "external", note="repo"),
        Deliverable(2, "b", "done", ("x",)),
        Deliverable(2, "c", "run", ("results/",)),
        Deliverable(3, "d", "planned", note="later"),
        Deliverable(4, "e", "done", ("y",)),
        Deliverable(4, "f", "planned", note="tag"),
    ]
    assert status_counts(items) == {"done": 2, "external": 1, "run": 1, "planned": 2}
    phases = by_phase(items)
    assert [phase_status(phases[p]) for p in (1, 2, 3, 4)] == [
        "external",
        "done",
        "planned",
        "partial",
    ]
    assert phase_status([]) == "missing"


@pytest.mark.parametrize(
    "data",
    [
        {"phases": [{"deliverables": []}]},
        {"phases": [{"phase": "1"}]},
        {"phases": [{"phase": 1, "deliverables": ["x"]}]},
        {
            "phases": [
                {
                    "phase": 1,
                    "deliverables": [{"spec": "x", "status": "done", "path": "a"}],
                }
            ]
        },
    ],
)
def test_yaml_shape_errors(data: object) -> None:
    with pytest.raises(InvariantError):
        deliverables_from_dict(data)


def test_yaml_single_path_string() -> None:
    items = deliverables_from_dict(
        {
            "phases": [
                {
                    "phase": 2,
                    "deliverables": [
                        {"spec": "doc", "status": "done", "paths": "docs/a.md"},
                        {"spec": "tag", "status": "planned", "note": "later"},
                    ],
                }
            ]
        }
    )
    assert items[0].paths == ("docs/a.md",) and items[1].note == "later"


def test_shipped_checklist_is_complete() -> None:
    q = load_quality_settings(ROOT / "config" / "quality.yaml")
    items = load_deliverables(ROOT / q.release.checklist)
    assert checklist_problems(items, lambda p: (ROOT / p).exists()) == []
    assert status_counts(items) == {"done": 57, "external": 12, "run": 3, "planned": 8}
    phases = by_phase(items)
    assert list(phases) == list(range(1, 17))
    assert (
        phase_status(phases[16]) == "planned" and phase_status(phases[15]) == "partial"
    )
    assert all((ROOT / d).is_file() for d in q.release.docs)
