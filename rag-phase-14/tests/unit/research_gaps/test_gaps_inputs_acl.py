"""Phase 12 ACL: shipped issues, IKE digest and project registry -> gap inputs."""

from dataclasses import dataclass

import pytest

from rag_core.projects.infrastructure.registry_json import JsonProjectRegistry
from rag_core.research_gaps.application.services import GapService
from rag_core.research_gaps.infrastructure.inputs_acl import (
    build_inputs,
    ike_items,
    subissue_views,
)
from tests.fixtures.issues.seed import seed_issues
from tests.fixtures.projects.samples import PROJECTS_DIR

pytestmark = [pytest.mark.research_gaps]


@dataclass(frozen=True)
class _Item:
    item_id: str
    lead: str | None
    lacks: tuple


@dataclass(frozen=True)
class _Digest:
    items: tuple


DIGEST = _Digest(
    (
        _Item(
            "AR-ISS-024/HW",
            "EX-SAEED-AKBARI",
            (("AR-HW-013", "not found"), ("AR-HW-013", "dup")),
        ),
        _Item("AR-ISS-024/WIN", None, (("AR-SW-019", "weak"),)),
        _Item("AR-ISS-024/WEB", "EX-NAZANIN-FARAHANI", ()),
    )
)


def test_ike_items_deduplicates_lack_targets() -> None:
    items = ike_items(DIGEST)
    assert items["AR-ISS-024/HW"] == ("EX-SAEED-AKBARI", ("AR-HW-013",))
    assert items["AR-ISS-024/WIN"] == ("", ("AR-SW-019",))
    assert ike_items(None) == {}


def test_subissue_views_of_the_shipped_case() -> None:
    views = {v.item_id: v for v in subissue_views(seed_issues(), ike_items(DIGEST))}
    assert set(views) == {
        "AR-ISS-024/HW",
        "AR-ISS-024/WIN",
        "AR-ISS-024/WEB",
        "AR-ISS-024/LEG",
    }
    win = views["AR-ISS-024/WIN"]
    assert (
        win.status == "blocked"
        and win.depends_on == ("AR-ISS-024/HW",)
        and win.lacks == ("AR-SW-019",)
    )
    assert (
        views["AR-ISS-024/HW"].owner_node == "N-HW-REP"
        and views["AR-ISS-024/HW"].executors
    )


def test_shipped_gaps_with_a_sample_digest() -> None:
    reg = JsonProjectRegistry(PROJECTS_DIR).load()
    report = GapService().detect(build_inputs(reg, seed_issues(), ike_items(DIGEST)))
    by_rule = report.by_rule()
    assert (
        by_rule["RG"] == 2
        and by_rule["DEP"] == 2
        and by_rule["CH"] == 3
        and by_rule["SC"] == 3
    )
    assert (
        by_rule["KL"] == 2
        and "EX" not in by_rule
        and "ST" not in by_rule
        and "EV" not in by_rule
    )
    assert {g.subject for g in report.gaps if g.rule == "DEP"} == {
        "AR-ISS-024/WIN",
        "AR-ISS-024/LEG",
    }
    assert report.count_by_issue() == {"AR-ISS-024": 4}


def test_gaps_without_ike_still_cover_registry_rules() -> None:
    reg = JsonProjectRegistry(PROJECTS_DIR).load()
    report = GapService().detect(build_inputs(reg, seed_issues(), None))
    assert "KL" not in report.by_rule() and report.by_rule()["RG"] == 2
    assert len(report.gaps) == 10
