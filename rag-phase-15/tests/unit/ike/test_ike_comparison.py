"""Issue-knowledge comparison: cited vs retrieved documents for one item."""

import pytest

from rag_core.ike.application.services import IkeService
from rag_core.ike.domain.comparison import compare_knowledge
from tests.fixtures.ike.samples import FakeSearch, sample_issue, search_result

pytestmark = [pytest.mark.ike, pytest.mark.ike_model]


def test_covered_suggested_missed_and_outside_scope() -> None:
    res = search_result(
        "N-HW-REP",
        ["AR-HW-012", "AR-HW-013", "AR-HW-012"],
        {"AR-HW-012", "AR-HW-013", "AR-SW-019"},
    )
    cmp = compare_knowledge(
        "AR-ISS-050/HW", ("AR-HW-012", "AR-HW-015", "AR-SW-019"), res
    )
    assert cmp.retrieved == ("AR-HW-012", "AR-HW-013")
    assert cmp.covered == ("AR-HW-012",)
    assert cmp.suggested == ("AR-HW-013",)
    assert cmp.missed == ("AR-SW-019",)
    assert cmp.outside_scope == ("AR-HW-015",)
    assert cmp.cited_recall == 0.5
    assert cmp.rank_of("AR-HW-013") == 2 and cmp.rank_of("AR-HW-015") is None


def test_lexical_evidence_floor() -> None:
    res = search_result("N-HW-REP", ["AR-HW-012"], {"AR-HW-012"}, lexical=2.0)
    assert not compare_knowledge("X/HW", ("AR-HW-012",), res).evidence
    assert compare_knowledge("X/HW", ("AR-HW-012",), res, min_lexical=1.5).evidence


def test_vector_score_decides_when_present() -> None:
    res = search_result(
        "N-HW-REP", ["AR-HW-012"], {"AR-HW-012"}, lexical=9.0, vector=0.30
    )
    cmp = compare_knowledge("X/HW", ("AR-HW-012",), res)
    assert cmp.mode == "hybrid" and not cmp.evidence
    assert compare_knowledge("X/HW", ("AR-HW-012",), res, min_vector=0.25).evidence


def test_no_visible_cited_document_gives_no_recall() -> None:
    res = search_result("N-SW-WEB", ["AR-SW-017"], {"AR-SW-017"})
    cmp = compare_knowledge("X/WEB", ("AR-HR-005",), res)
    assert cmp.outside_scope == ("AR-HR-005",) and cmp.cited_recall is None
    data = cmp.to_dict()
    assert data["suggested"] == ["AR-SW-017"] and data["cited_recall"] is None


def test_unknown_scope_never_marks_outside() -> None:
    res = search_result("N-SW-WEB", [], set())
    cmp = compare_knowledge("X/WEB", ("AR-SW-017",), res)
    assert cmp.outside_scope == () and cmp.missed == ("AR-SW-017",) and not cmp.evidence


def test_service_compares_every_subissue_from_its_owner_node() -> None:
    search = FakeSearch(
        {
            "N-HW-REP": search_result(
                "N-HW-REP", ["AR-HW-012"], {"AR-HW-012", "AR-HW-015"}
            )
        }
    )
    out = IkeService(search, top_k=6).compare(sample_issue())
    assert list(out) == ["AR-ISS-050/HW", "AR-ISS-050/WIN", "AR-ISS-050/WEB"]
    assert [c[1] for c in search.calls] == ["N-HW-REP", "N-SW-WIN", "N-SW-WEB"]
    assert all(c[2] == 6 for c in search.calls)
    assert "Hardware: RAID controller" in search.calls[0][0]
    assert sample_issue().sub_items[0].title_fa in search.calls[0][0]
    assert out["AR-ISS-050/HW"].covered == ("AR-HW-012",)
    assert not out["AR-ISS-050/WEB"].evidence


def test_service_without_search_port_compares_nothing() -> None:
    assert IkeService().compare(sample_issue()) == {}
