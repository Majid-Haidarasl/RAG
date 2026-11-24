"""Phase 13 template-first RFP generation from key issues, gaps and the blueprint."""

import re

import pytest

from rag_core.rfp.domain.blueprint import SECTION_ORDER
from rag_core.rfp.domain.generator import (
    DEFAULT_HEADINGS,
    MAX_GAPS,
    GapView,
    build_rfp,
    relevant_gaps,
    select_candidates,
)
from tests.fixtures.rfp.samples import (
    CYCLE,
    MANDATORY,
    TARGETS,
    gap_views,
    item_view,
    key_views,
    shipped_blueprint,
)

pytestmark = [pytest.mark.rfp_gen]


def candidates():  # noqa: ANN201
    return select_candidates(
        key_views(), [shipped_blueprint()], ("procurement",), TARGETS
    )


def draft(language: str = "en", **kw):  # noqa: ANN003, ANN201
    key = {k.issue_id: k for k in key_views()}
    return build_rfp(
        shipped_blueprint(),
        candidates(),
        key,
        gap_views(),
        language,
        CYCLE,
        item_view(),
        **kw,
    )


def test_candidates_target_procurement_and_not_sourcing() -> None:
    got = [(c.issue_id, c.reason, c.blueprint_id, c.item_id) for c in candidates()]
    assert got == [
        ("AR-ISS-024", "target", "BP-WEB-REPORTING", "AR-ISS-024/WEB"),
        ("AR-ISS-031", "not_sourcing", "", ""),
        ("AR-ISS-035", "procurement", "BP-WEB-REPORTING", ""),
    ]
    assert [c.has_rfp for c in candidates()] == [True, False, True]


def test_candidates_without_a_blueprint_or_targets() -> None:
    got = select_candidates(
        key_views(), [shipped_blueprint()], ("procurement", "schedule"), {}
    )
    assert [(c.issue_id, c.reason) for c in got] == [
        ("AR-ISS-024", "not_sourcing"),
        ("AR-ISS-031", "no_blueprint"),
        ("AR-ISS-035", "procurement"),
    ]
    assert all(
        not c.has_rfp
        for c in select_candidates(key_views(), [], ("procurement",), TARGETS)
    )


def test_candidates_are_ordered_by_rank() -> None:
    got = select_candidates(
        list(reversed(key_views())), [shipped_blueprint()], ("procurement",), TARGETS
    )
    assert [c.issue_id for c in got] == ["AR-ISS-024", "AR-ISS-031", "AR-ISS-035"]
    assert got[0].to_dict() == {
        "issue_id": "AR-ISS-024",
        "reason": "target",
        "blueprint_id": "BP-WEB-REPORTING",
        "item_id": "AR-ISS-024/WEB",
    }


def test_relevant_gaps_skip_sibling_sub_issues_and_cap() -> None:
    assert [
        g.gap_id
        for g in relevant_gaps(
            gap_views(), ("AR-ISS-024", "AR-ISS-035"), "AR-ISS-024/WEB"
        )
    ] == ["KL:AR-ISS-024/WEB", "UI:AR-ISS-035"]
    many = [GapView(f"G{i}", "AR-ISS-035", "low", "t", "ت") for i in range(10)]
    assert len(relevant_gaps(many, ("AR-ISS-035",), "")) == MAX_GAPS


def test_english_rfp_lines() -> None:
    d = draft("en")
    assert (
        d.facts[0]
        == "RFP AR-RFP-1403-07: Warehouse web reporting module (Azarpakhsh). Owner N-SW; cycle 1403-Q2."
    )
    assert d.facts[1] == (
        "AR-ISS-024 is key issue 1 of cycle 1403-Q2: Azarpakhsh warehouse delivery delay; score "
        "82.75 of 100; main factors: urgency 12, risk 12, priority 11.25; reason for the RFP: "
        "configured target."
    )
    assert d.facts[2].endswith(
        "score 30.17 of 100; main factors: priority 7.5, urgency 7.5, risk 6; reason for the "
        "RFP: procurement."
    )
    assert (
        d.facts[3]
        == "Sub-issue AR-ISS-024/WEB (in_progress), owner N-SW-WEB: Web reporting module."
    )
    assert (
        d.facts[4]
        == "Gap KL:AR-ISS-024/WEB (medium): Knowledge lack on the web reporting module."
    )
    assert "[REQ-NEED] (mandatory) Solicitation AR-RFP-1403-07" in d.text
    assert "[REQ-ARCHITECTURE] (recommended) AR-SW-016 is authoritative" in d.text
    assert (
        "Criterion CRT-TECH (Technical): weight 60%; considers existing-API compatibility"
        in d.text
    )
    assert (
        "LNK-ARCHITECTURE: N-SW-WEB (EX-NAZANIN-FARAHANI) — reviews architectural compatibility"
        in d.text
    )
    assert "LNK-LIBRARY: N-LIB — stores requirements" in d.text


def test_persian_rfp_lines() -> None:
    d = draft("fa")
    assert d.facts[0].startswith(
        f"درخواست پیشنهاد AR-RFP-1403-07: {shipped_blueprint().title('fa')}."
    )
    assert (
        "مسئله کلیدی 1 چرخه 1403-Q2" in d.facts[1]
        and "دلیل درخواست: هدف تعیین‌شده" in d.facts[1]
    )
    assert "دلیل درخواست: تأمین از بیرون" in d.facts[2]
    assert "(در جریان)" in d.facts[3] and "(شدت متوسط)" in d.facts[4]
    assert "[REQ-NEED] (الزامی)" in d.text and "[REQ-SECURITY] (توصیه‌شده)" in d.text
    assert "وزن 60٪" in d.text and "وزن 40٪" in d.text


def test_counts_and_ids() -> None:
    d = draft("en")
    assert d.items == ("AR-RFP-1403-07", "AR-ISS-024/WEB", "AR-ISS-024", "AR-ISS-035")
    assert d.gaps == (*MANDATORY, "AR-ISS-024/WEB", "AR-ISS-035")
    assert d.issues == ("AR-ISS-024", "AR-ISS-035") and d.gap_ids == (
        "KL:AR-ISS-024/WEB",
        "UI:AR-ISS-035",
    )
    assert (
        len(d.facts) == 26
        and len(d.requirement_ids) == 11
        and d.sections == SECTION_ORDER
    )


def test_text_is_facts_under_headings() -> None:
    d = draft("en")
    lines = d.text.splitlines()
    headings = [line for line in lines if line.endswith(":") and line not in d.facts]
    assert [line for line in lines if line not in headings] == list(d.facts)
    assert len(headings) == 16 and headings[0] == "Request for proposal:"


def test_sections_follow_the_fixed_order() -> None:
    d = draft("en")
    positions = [d.text.index(f"{DEFAULT_HEADINGS[s][0]}:") for s in SECTION_ORDER]
    assert positions == sorted(positions)


def test_custom_headings_replace_defaults() -> None:
    d = draft("fa", headings={"need": ("Need!", "نیاز سازمان")})
    assert "نیاز سازمان:" in d.text.splitlines()


def test_every_number_and_id_in_the_text_is_in_the_facts() -> None:
    for lang in ("fa", "en"):
        d = draft(lang)
        facts = "\n".join(d.facts)
        for token in re.findall(r"AR-[A-Z]+-[0-9A-Z/-]+|\d+(?:\.\d+)?", d.text):
            assert token in facts, token


def test_without_item_uses_blueprint_item_id() -> None:
    key = {k.issue_id: k for k in key_views()}
    d = build_rfp(
        shipped_blueprint(), candidates(), key, gap_views(), "en", CYCLE, None
    )
    assert d.items[1] == "AR-ISS-024/WEB" and not any(
        f.startswith("Sub-issue") for f in d.facts
    )


def test_to_dict_and_sizes() -> None:
    d = draft("en")
    data = d.to_dict()
    assert (
        data["rfp_id"] == "AR-RFP-1403-07"
        and data["words"] == d.words
        and data["chars"] == len(d.text)
    )
    assert (
        d.chars > 3000
    )  # an RFP is longer than a Phase 10 summary (judged with judging.max_rfp_chars)
