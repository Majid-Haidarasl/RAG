"""Deterministic package text per detail level (facts, English, Persian, fields)."""

import pytest

from tests.fixtures.transfer.samples import (
    built,
    ceo,
    deputy,
    draft_for,
    empty_team,
    team_hw,
    team_mob,
    team_win,
)

pytestmark = [pytest.mark.transfer, pytest.mark.transfer_pkg]


def sw_children():  # noqa: ANN201
    return [built(team_win(), "N-SW", 2), built(team_mob(), "N-SW", 2)]


def test_technical_facts_header_and_counts() -> None:
    d = draft_for(team_hw(), "N-HW", 2)
    assert d.facts[0] == (
        "package 1403-Q2: from N-HW-REP to N-HW | receiving layer L2 | "
        "detail level technical_summary"
    )
    assert d.facts[2].startswith(
        "counts: issues 2 | items 2 | open 1 | blocked 0 | reserved decisions 0 | "
        "knowledge gaps 1 | omitted 0 | documents 3"
    )
    assert "executor Saeed Akbari (سعید اکبری): 14 h/week" in d.facts


def test_technical_english_item_lines() -> None:
    text = draft_for(team_hw(), "N-HW", 2).text("en")
    assert (
        "- AR-ISS-024/HW: lead Saeed Akbari; in_progress; Hardware; owner N-HW-REP; collaborators "
        "Farzaneh Javadi; documents AR-HW-012, AR-HW-013; knowledge gaps AR-HW-013."
    ) in text
    assert "  AR-ISS-024/HW is part of AR-ISS-024 (progress 62%)." in text
    assert (
        "- AR-ISS-034: lead Saeed Akbari; closed; Workstation startup faults; owner N-HW-REP."
        in text
    )
    assert (
        "Capacity: 2 executors (Farzaneh Javadi unit planning, Saeed Akbari 14 h/week)."
        in text
    )
    assert (
        text.splitlines()[-1]
        == "Sources: AR-HW-012@1.2, AR-HW-013@1.0, AR-ISS-024@1.0."
    )


def test_technical_persian_text() -> None:
    text = draft_for(team_hw(), "N-HW", 2).text("fa")
    assert text.startswith(
        "بستهٔ انتقال دانش 1403-Q2 از N-HW-REP به N-HW (سطح خلاصهٔ فنی)."
    )
    assert (
        "- AR-ISS-024/HW: مجری اصلی سعید اکبری؛ در جریان؛ سخت‌افزار؛ مالک N-HW-REP؛ همکاران فرزانه جوادی"
        in text
    )
    assert "کمبود دانش AR-HW-013." in text
    assert (
        "ظرفیت: 2 مجری (فرزانه جوادی با برنامه‌ریزی واحد، سعید اکبری 14 ساعت در هفته)."
        in text
    )


def test_managerial_groups_by_issue() -> None:
    d = draft_for(
        deputy("N-SW", "Software deputy"),
        "N-CEO",
        1,
        sw_children(),
        expected_children=2,
    )
    text = d.text("en")
    assert (
        "AR-ISS-024: Azarpakhsh delivery delay; status in_progress; priority P1; progress 62%; due 1403-07-15; "
        "decision amount 850 million toman."
    ) in text
    assert (
        "- AR-ISS-024/WIN: lead Roozbeh Mohseni; blocked; owner N-SW-WIN; depends on AR-ISS-024/HW."
        in text
    )
    assert (
        "- AR-ISS-031: lead Nima Rad; triaged; Mobile app login failures; owner N-SW-MOB."
        in text
    )
    assert "Knowledge gaps: AR-ISS-024/WIN -> AR-HW-015." in text
    assert (
        "Capacity: 3 executors, 3 with published hours (20 h/week), 0 by unit planning."
        in text
    )
    assert "Received packages: 2 of 2." in text
    assert "Roozbeh Mohseni 10 h/week" not in text


def test_executive_board_brief() -> None:
    sw = built(deputy("N-SW", "Software deputy"), "N-CEO", 1, sw_children())
    d = draft_for(ceo(), "N-BRD", 0, [sw], expected_children=1)
    text = d.text("en")
    assert text.startswith("Board brief 1403-Q2 from N-CEO to N-BRD (executive).")
    assert (
        "Open issues 2, blocked items 1, reserved decisions 0, knowledge gaps 1."
        in text
    )
    assert (
        "- AR-ISS-024: Azarpakhsh delivery delay; status in_progress; priority P1; progress 62%; due 1403-07-15; "
        "decision amount 850 million toman; blocked 1 of 1 items; items AR-ISS-024/WIN."
    ) in text
    assert "Decisions requested: AR-ISS-024: decision amount 850 million toman." in text
    assert "Roozbeh" not in text and "lead" not in text
    assert d.text("fa").startswith("گزارش هیئت‌مدیره 1403-Q2 از N-CEO به N-BRD")


def test_expectations_follow_the_level() -> None:
    tech = draft_for(team_hw(), "N-HW", 2).rendered
    assert tech.expected_items == ("AR-ISS-024/HW", "AR-ISS-034")
    assert tech.expected_leads[0] == ("AR-ISS-024/HW", ("Saeed Akbari", "سعید اکبری"))
    assert tech.expected_gaps == ("AR-HW-013",)
    sw = built(deputy("N-SW", "Software deputy"), "N-CEO", 1, sw_children())
    exe = draft_for(ceo(), "N-BRD", 0, [sw]).rendered
    assert exe.expected_leads == () and exe.expected_gaps == ()


def test_texts_have_no_tables_or_fences() -> None:
    d = draft_for(team_hw(), "N-HW", 2)
    for lang in ("fa", "en"):
        assert "|" not in d.text(lang) and "```" not in d.text(lang)


def test_empty_node_text() -> None:
    d = draft_for(empty_team(), "N-HW", 2)
    assert "No open or recent issue is held by this node." in d.text("en")
    assert "Capacity: 1 executors (Ali Nouri unit planning)." in d.text("en")
    assert "Sources: none." in d.text("en")
    assert d.rendered.expected_items == ()


def test_fields_for_l0_package() -> None:
    sw = built(deputy("N-SW", "Software deputy"), "N-CEO", 1, sw_children())
    fields = draft_for(ceo(), "N-BRD", 0, [sw]).package.fields
    assert fields["risks"] == "AR-ISS-024/WIN: blocked"
    assert (
        fields["decisions_requested"] == "AR-ISS-024: decision amount 850 million toman"
    )
    assert (
        fields["source_references"] == "AR-ISS-024@1.0, AR-ISS-031@1.0, AR-SW-019@1.1"
    )
    assert fields["key_issues"] == "AR-ISS-024/WIN, AR-ISS-031"
    assert fields["counts"].endswith("received 1 of 0")
