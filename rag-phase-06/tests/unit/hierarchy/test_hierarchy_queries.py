"""Path, ancestor, descendant, depth and lowest-common-ancestor queries."""

import pytest

from rag_core.shared_kernel.identifiers import NodeIdentifier
from tests.fixtures.hierarchy.registry import shipped_registry

pytestmark = [pytest.mark.hierarchy, pytest.mark.registry]

N = NodeIdentifier


@pytest.fixture(scope="module")
def org():
    return shipped_registry().organization


def test_path_from_root(org) -> None:
    assert [str(n) for n in org.path(N("N-HW-REP"))] == ["N-BRD", "N-CEO", "N-HW", "N-HW-REP"]


def test_ancestors_nearest_first(org) -> None:
    assert [str(a.identifier) for a in org.ancestors(N("N-ADM-HR"))] == ["N-ADM", "N-CEO", "N-BRD"]
    assert org.ancestors(N("N-BRD")) == []


def test_depth_differs_from_layer_for_the_library(org) -> None:
    assert org.depth(N("N-BRD")) == 0
    assert org.depth(N("N-SW-WEB")) == 3
    assert org.depth(N("N-LIB")) == 2


def test_descendants_and_children(org) -> None:
    assert len(org.descendants(N("N-CEO"))) == 19
    assert {str(c.identifier) for c in org.children_of(N("N-ADM"))} == {
        "N-ADM-HR", "N-ADM-FIN", "N-ADM-LEG", "N-ADM-SRV", "N-ADM-SEC",
    }
    assert org.descendants(N("N-SW-WEB")) == []


@pytest.mark.parametrize(
    ("nodes", "expected"),
    [
        (("N-SW-WEB", "N-SW-MOB"), "N-SW"),
        (("N-SW-WEB", "N-HW-REP"), "N-CEO"),
        (("N-SW-WEB", "N-LIB"), "N-CEO"),
        (("N-SW-WEB", "N-SW"), "N-SW"),
        (("N-ADM-HR", "N-BRD"), "N-BRD"),
        (("N-HW-REP", "N-HW-ADV", "N-HW-ASM"), "N-HW"),
    ],
)
def test_lowest_common_ancestor(org, nodes, expected: str) -> None:
    assert str(org.lowest_common_ancestor(*(N(n) for n in nodes))) == expected


def test_is_ancestor(org) -> None:
    assert org.is_ancestor(N("N-CEO"), N("N-LIB"))
    assert not org.is_ancestor(N("N-SW"), N("N-HW-REP"))


def test_leaves_are_execution_units_and_the_library(org) -> None:
    leaves = {str(n.identifier) for n in org.leaves()}
    assert "N-LIB" in leaves and "N-SW" not in leaves
    assert all(org.get(N(n)).layer.value in (3, 4) for n in leaves)
