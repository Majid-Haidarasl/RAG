"""Phase 13 inputs ACL: Phase 7 issues, Phase 12 ranking and gaps -> generator views."""

from types import SimpleNamespace as NS

import pytest

from rag_core.rfp.infrastructure.inputs_acl import executor_nodes, gap_views, item_views, key_issue_views

pytestmark = [pytest.mark.rfp_gen]


def score(issue_id: str, rank: int, key: bool) -> NS:
    return NS(issue_id=issue_id, title_en=f"{issue_id} en", title_fa=f"{issue_id} fa", rank=rank, score=40.5,
              key=key, top_factors=lambda: [("risk", 12.0)])


def issue(issue_id: str, category: str, subs: list | None = None) -> NS:
    return NS(identifier=issue_id, category=NS(value=category), status=NS(value="open"), owning_node="N-SW",
              subissues=subs or [])


def test_only_key_rows_become_views() -> None:
    views = key_issue_views([score("AR-ISS-024", 1, True), score("AR-ISS-040", 4, False)],
                            [issue("AR-ISS-024", "delivery_delay")])
    assert [(v.issue_id, v.category, v.status, v.rank, v.top_factors) for v in views] == [
        ("AR-ISS-024", "delivery_delay", "open", 1, (("risk", 12.0),))]


def test_item_owner_falls_back_to_the_issue_owner() -> None:
    subs = [NS(identifier="AR-ISS-024/WEB", status=NS(value="in_progress"), owner_node="N-SW-WEB", title="Web",
               title_fa="وب"),
            NS(identifier="AR-ISS-024/HW", status=NS(value="blocked"), owner_node=None, title="HW", title_fa="")]
    items = item_views([issue("AR-ISS-024", "delivery_delay", subs)])
    assert items["AR-ISS-024/WEB"].owner_node == "N-SW-WEB" and items["AR-ISS-024/HW"].owner_node == "N-SW"
    assert items["AR-ISS-024/HW"].title_fa == ""


def test_gap_views_keep_issue_gaps_only() -> None:
    gaps = [NS(gap_id="KL:X", subject="AR-ISS-024/WEB", severity=NS(value="medium"), title_en="a", title_fa="ب",
               issue_id="AR-ISS-024"),
            NS(gap_id="RG:Y", subject="RES-PHOTO", severity=NS(value="low"), title_en="c", title_fa="د", issue_id="")]
    assert [(g.gap_id, g.severity) for g in gap_views(gaps)] == [("KL:X", "medium")]


def test_executor_nodes() -> None:
    assert executor_nodes([NS(identifier="EX-A", home_node="N-SW-WEB")]) == {"EX-A": "N-SW-WEB"}
