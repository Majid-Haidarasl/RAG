"""Per-layer knowledge-transfer requirement invariants."""

import pytest

from rag_core.hierarchy.domain.model import Layer
from rag_core.hierarchy.domain.transfer import TransferDirection, TransferRequirement
from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.layer import LayerIndex
from tests.fixtures.hierarchy.registry import shipped_registry

pytestmark = [pytest.mark.hierarchy, pytest.mark.registry]

L = LayerIndex


def _req(**kw) -> TransferRequirement:
    base = dict(
        layer=L(3),
        direction=TransferDirection.UP,
        target=L(2),
        must_hand_over="Executor package",
        min_artefacts=("TransferPackage CSV", "technical summary"),
        approvals=("team lead",),
        required_feedback="VP returns priorities",
        sources=("AR-TRN-026",),
    )
    base.update(kw)
    return TransferRequirement(**base)


def test_complete_requirement_has_no_gaps() -> None:
    assert _req().is_complete


@pytest.mark.parametrize(
    ("kw", "gap"),
    [
        ({"min_artefacts": ("only one",)}, "min_artefacts<2"),
        ({"approvals": ()}, "approvals"),
        ({"required_feedback": " "}, "required_feedback"),
        ({"sources": ()}, "sources"),
    ],
)
def test_gaps(kw, gap: str) -> None:
    assert gap in _req(**kw).gaps()


def test_upward_transfer_must_target_the_parent_layer() -> None:
    with pytest.raises(InvariantError, match="upward"):
        _req(target=L(1))


def test_downward_transfer_from_board_goes_to_l1_only() -> None:
    _req(layer=L(0), direction=TransferDirection.DOWN, target=L(1))
    with pytest.raises(InvariantError, match="down"):
        _req(layer=L(0), direction=TransferDirection.DOWN, target=L(2))


def test_layer_rejects_requirement_of_another_layer() -> None:
    with pytest.raises(InvariantError, match="another layer"):
        Layer(L(2), "L2", "Deputies", "معاونت‌ها", transfer=_req())


def test_check_package_lists_missing_artefacts_and_approvals() -> None:
    req = _req()
    assert req.check_package({"TransferPackage CSV"}, set()) == [
        "artefact: technical summary",
        "approval: team lead",
    ]
    assert req.check_package(set(req.min_artefacts), set(req.approvals)) == []


def test_shipped_l3_requirement_lists_artefacts_and_approvals() -> None:
    l3 = shipped_registry().organization.layers[3].transfer
    assert l3.direction is TransferDirection.UP and l3.target == L(2)
    assert len(l3.min_artefacts) >= 2 and l3.approvals
