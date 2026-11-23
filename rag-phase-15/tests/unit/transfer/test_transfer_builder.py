"""TransferPackageBuilder: merge, drop closed, limit, trim, citations and the Phase 3 aggregate."""

from dataclasses import replace

import pytest

from rag_core.shared_kernel.errors import InvariantError
from rag_core.transfer.domain.builder import TransferPackageBuilder
from rag_core.transfer.domain.items import NodeKnowledge
from rag_core.transfer.domain.levels import RuleBook
from rag_core.transfer.domain.model import PackageStatus, TransferDetailLevel
from tests.fixtures.transfer.samples import (
    CYCLE,
    VERSIONS,
    built,
    ceo,
    deputy,
    draft_for,
    hw_item,
    item,
    team_hw,
    team_mob,
    team_win,
)

pytestmark = [pytest.mark.transfer, pytest.mark.transfer_pkg]


def test_technical_package_keeps_closed_items() -> None:
    d = draft_for(team_hw(), "N-HW", 2)
    assert [i.item_id for i in d.items] == ["AR-ISS-024/HW", "AR-ISS-034"]
    assert d.dropped_closed == () and d.omitted == ()
    assert d.detail_level == "technical_summary"
    assert d.package.status is PackageStatus.DRAFT
    assert d.package.detail_level is TransferDetailLevel.TECHNICAL_SUMMARY


def test_managerial_package_drops_closed_and_merges() -> None:
    hw = built(team_hw(), "N-HW", 2)
    adv = NodeKnowledge("N-HW-ADV", 3, "Advice team", items=(hw_item(origin="N-HW-ADV"),))
    adv_pkg = built(adv, "N-HW", 2)
    d = draft_for(deputy(), "N-CEO", 1, [adv_pkg, hw], expected_children=2)
    assert [i.item_id for i in d.items] == ["AR-ISS-024/HW"]
    assert d.items[0].role.value == "owner"
    assert d.dropped_closed == ("AR-ISS-034",)
    assert d.received_from == ("N-HW-ADV", "N-HW-REP")


def test_executive_limit_lists_omitted_issues() -> None:
    extra = [item(f"AR-ISS-04{k}", "N-SW", title_en=f"Issue {k}", title_fa="مسئله") for k in range(4)]
    sw_dep = NodeKnowledge("N-SW", 2, "Software deputy", items=tuple(extra))
    sw = built(sw_dep, "N-CEO", 1, [built(team_win(), "N-SW", 2)])
    d = draft_for(ceo(), "N-BRD", 0, [sw])
    assert len({i.parent_id for i in d.items}) == 3
    assert d.items[0].item_id == "AR-ISS-024/WIN"
    assert d.omitted == ("AR-ISS-042", "AR-ISS-043")


def test_child_omissions_are_carried_upward() -> None:
    win = built(team_win(), "N-SW", 2)
    win.draft.omitted = ("AR-ISS-099",)
    d = draft_for(deputy("N-SW", "Software deputy"), "N-CEO", 1, [win])
    assert "AR-ISS-099" in d.omitted


def test_capacity_per_person_only_at_technical_level() -> None:
    tech = draft_for(team_hw(), "N-HW", 2)
    assert len(tech.capacity.people) == 2
    mgr = draft_for(deputy(), "N-CEO", 1, [built(team_hw(), "N-HW", 2)])
    assert mgr.capacity.people == ()
    assert (mgr.capacity.executors, mgr.capacity.hours_per_week) == (3, 18)


def test_citations_need_an_active_version() -> None:
    d = TransferPackageBuilder({}).build(CYCLE, team_hw(), "N-HW", RuleBook().for_layer(2))
    assert d.citations == ("AR-HW-012@1.2",)
    full = draft_for(team_hw(), "N-HW", 2)
    assert full.citations == ("AR-HW-012@1.2", "AR-HW-013@1.0", "AR-ISS-024@1.0")
    assert [str(c.document_id) for c in full.package.citations] == ["AR-HW-012", "AR-HW-013", "AR-ISS-024"]


def test_word_limit_trims_units() -> None:
    many = tuple(item(f"AR-ISS-05{k}", "N-SW-MOB", title_en="Long title " + "word " * 40, title_fa="عنوان")
                 for k in range(6))
    node = NodeKnowledge("N-SW-MOB", 3, "Mobile team", items=many)
    rule = replace(RuleBook().for_layer(2), max_words=200)
    d = TransferPackageBuilder(VERSIONS).build(CYCLE, node, "N-SW", rule)
    assert d.trimmed > 0
    assert all(d.words(lang) <= 200 for lang in ("fa", "en"))
    assert len(d.items) + len(d.omitted) == 6


def test_package_too_long_even_with_one_unit_raises() -> None:
    huge = item("AR-ISS-051", "N-SW-MOB", title_en="word " * 300, title_fa="عنوان")
    node = NodeKnowledge("N-SW-MOB", 3, "Mobile team", items=(huge,))
    rule = replace(RuleBook().for_layer(2), max_words=60)
    with pytest.raises(InvariantError):
        TransferPackageBuilder(VERSIONS).build(CYCLE, node, "N-SW", rule)


def test_self_target_is_rejected() -> None:
    with pytest.raises(InvariantError):
        draft_for(team_mob(), "N-SW-MOB", 2)


def test_content_dict_is_stable() -> None:
    a = draft_for(team_hw(), "N-HW", 2).content_dict()
    b = draft_for(team_hw(), "N-HW", 2).content_dict()
    assert a == b
    assert a["fields"]["key_issues"] == "AR-ISS-024/HW, AR-ISS-034"
    assert "created_at" not in a
