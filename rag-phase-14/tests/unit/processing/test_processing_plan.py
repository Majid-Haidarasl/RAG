"""Bottom-up processing plan: leaves first, root and repository skipped."""

import pytest

from rag_core.processing.domain.plan import (
    PARENT_RETIRED_REASON,
    REPOSITORY_REASON,
    RETIRED_REASON,
    ROOT_REASON,
    TreeNode,
    build_plan,
)
from rag_core.shared_kernel.errors import InvariantError

pytestmark = [pytest.mark.processing]


def tree() -> list[TreeNode]:
    return [
        TreeNode("N-BRD", 0, None),
        TreeNode("N-CEO", 1, "N-BRD"),
        TreeNode("N-HW", 2, "N-CEO"),
        TreeNode("N-SW", 2, "N-CEO"),
        TreeNode("N-HW-REP", 3, "N-HW"),
        TreeNode("N-HW-ADV", 3, "N-HW"),
        TreeNode("N-SW-WIN", 3, "N-SW"),
        TreeNode("N-LIB", 4, "N-CEO", repository=True),
    ]


def test_plan_orders_leaves_first_and_ceo_last() -> None:
    plan = build_plan(tree())
    assert plan.senders == ("N-HW-ADV", "N-HW-REP", "N-SW-WIN", "N-HW", "N-SW", "N-CEO")
    assert [s.order for s in plan.steps] == [1, 2, 3, 4, 5, 6]
    assert plan.is_bottom_up()


def test_plan_targets_and_layers() -> None:
    plan = build_plan(tree())
    rep = plan.step_of("N-HW-REP")
    assert (rep.target_node, rep.source_layer, rep.target_layer) == ("N-HW", 3, 2)
    assert plan.step_of("N-CEO").target_node == "N-BRD"
    assert plan.children_of("N-HW") == ("N-HW-ADV", "N-HW-REP")
    assert plan.children_of("N-CEO") == ("N-HW", "N-SW")


def test_root_and_repository_are_skipped() -> None:
    skipped = {s.node_id: s.reason for s in build_plan(tree()).skipped}
    assert skipped == {"N-BRD": ROOT_REASON, "N-LIB": REPOSITORY_REASON}


def test_retired_node_and_its_children_are_skipped() -> None:
    nodes = [*tree()[:-1]]
    nodes[2] = TreeNode("N-HW", 2, "N-CEO", active=False)
    plan = build_plan(nodes)
    skipped = {s.node_id: s.reason for s in plan.skipped}
    assert skipped["N-HW"] == RETIRED_REASON
    assert skipped["N-HW-REP"] == PARENT_RETIRED_REASON
    assert "N-HW-REP" not in plan.senders


def test_step_of_unknown_node_raises() -> None:
    with pytest.raises(KeyError):
        build_plan(tree()).step_of("N-NOPE")


@pytest.mark.parametrize(
    "nodes",
    [
        [TreeNode("N-BRD", 0, None), TreeNode("N-BRD", 1, None)],
        [TreeNode("N-BRD", 0, None), TreeNode("N-CEO", 0, None)],
        [TreeNode("N-BRD", 0, None), TreeNode("N-CEO", 1, "N-GONE")],
        [
            TreeNode("N-BRD", 0, None),
            TreeNode("N-A", 1, "N-B"),
            TreeNode("N-B", 1, "N-A"),
        ],
    ],
    ids=["duplicate", "two_roots", "unknown_parent", "cycle"],
)
def test_invalid_trees_are_rejected(nodes: list[TreeNode]) -> None:
    with pytest.raises(InvariantError):
        build_plan(nodes)
