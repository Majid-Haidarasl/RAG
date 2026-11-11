import pytest

from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.layer import LayerIndex

pytestmark = pytest.mark.shared_kernel


def test_layer_index_code_and_adjacency() -> None:
    parent, child = LayerIndex(2), LayerIndex(3)
    assert str(parent) == "L2"
    assert parent.is_adjacent_parent_of(child)
    assert not child.is_adjacent_parent_of(parent)
    assert not LayerIndex(1).is_adjacent_parent_of(LayerIndex(3))


def test_layer_index_rejects_negative_and_bool() -> None:
    with pytest.raises(InvariantError):
        LayerIndex(-1)
    with pytest.raises(InvariantError):
        LayerIndex(True)  # type: ignore[arg-type]
