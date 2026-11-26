"""The real ArmanRayan registry → processing plan (21 nodes, 19 senders)."""

from pathlib import Path

import pytest

from rag_core.hierarchy.application.workflows import load_and_validate
from rag_core.processing.domain.plan import REPOSITORY_REASON, ROOT_REASON, build_plan
from rag_core.processing.infrastructure.hierarchy_acl import tree_nodes

pytestmark = [pytest.mark.processing]

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def plan():
    loaded = load_and_validate(ROOT / "data" / "registry")
    assert loaded.organization is not None
    return build_plan(tree_nodes(loaded.organization))


def test_real_plan_has_19_senders_bottom_up(plan) -> None:
    assert len(plan.steps) == 19
    assert plan.is_bottom_up()
    assert plan.steps[-1].source_node == "N-CEO"
    assert plan.steps[-1].target_node == "N-BRD"


def test_real_plan_targets_per_layer(plan) -> None:
    by_target: dict[int, int] = {}
    for s in plan.steps:
        by_target[s.target_layer] = by_target.get(s.target_layer, 0) + 1
    assert by_target == {2: 15, 1: 3, 0: 1}
    assert {s.node_id: s.reason for s in plan.skipped} == {
        "N-BRD": ROOT_REASON,
        "N-LIB": REPOSITORY_REASON,
    }
    assert len(plan.children_of("N-SW")) == 6
