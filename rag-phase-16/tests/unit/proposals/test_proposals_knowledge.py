"""Phase 13 links back to node knowledge: who holds each part, where the outcome is recorded."""

import pytest

from rag_core.proposals.domain.evaluation import evaluate
from rag_core.proposals.domain.knowledge import link_knowledge
from tests.fixtures.rfp.samples import EXECUTORS, NODES, shipped_blueprint, shipped_registry, with_link

pytestmark = [pytest.mark.proposals]


def bundle(bp=None, nodes=NODES, executors=EXECUTORS):  # noqa: ANN001, ANN201
    bp = bp or shipped_blueprint()
    reg = shipped_registry()
    return link_knowledge(bp, reg, evaluate(bp, reg), frozenset(nodes), executors)


def test_every_link_is_valid_and_the_outcome_is_recorded() -> None:
    k = bundle()
    assert k.ok and k.valid == len(k.links) == 7
    assert k.nodes == ["N-SW-WEB", "N-SW-UX", "N-SW-SUP", "N-ADM-LEG", "N-ADM-FIN", "N-LIB"]
    assert len(k.executors) == 6
    o = k.outcome
    assert o is not None and (o.item, o.selected, o.weighted, o.owner_node) == ("AR-ISS-024/WEB", "PRP-A", "78.8",
                                                                                "N-SW")
    assert o.issues == ("AR-ISS-024", "AR-ISS-035") and o.evidence == ("AR-RFP-025",)


def test_bad_links_are_marked() -> None:
    for change, problem in [({"node": "N-XYZ"}, "unknown_node"), ({"executor": "EX-NOBODY"}, "unknown_executor"),
                            ({"executor": "EX-REZA-ABBASI"}, "executor_node_mismatch"),
                            ({"requirements": ("REQ-NOPE",)}, "unknown_requirement")]:
        k = bundle(with_link(shipped_blueprint(), "LNK-DESIGN", **change))
        bad = [r for r in k.links if not r.valid]
        assert [(r.link_id, r.problem) for r in bad] == [("LNK-DESIGN", problem)] and not k.ok


def test_to_dict() -> None:
    data = bundle().to_dict()
    assert data["ok"] is True and data["outcome"]["item"] == "AR-ISS-024/WEB"  # type: ignore[index]
    assert data["links"][0]["link"] == "LNK-ARCHITECTURE"  # type: ignore[index]
