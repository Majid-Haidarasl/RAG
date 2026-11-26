"""Phase 10 rule judge: answers, refusals and IKE summaries scored without a model."""

from pathlib import Path

import pytest

from rag_core.ike.application.services import IkeService, IkeSummaryService
from rag_core.ike.domain.summary import digest, facts_lines
from rag_core.judging.domain.cases import SourceBlock
from rag_core.judging.domain.rubric import Criterion, Rubric, default_rubric
from rag_core.judging.domain.rule_judge import (
    RuleBasedJudge,
    RuleJudgeConfig,
    citation_valid,
    first_item,
)
from rag_core.judging.domain.text import CitedRef
from rag_core.judging.infrastructure.calibration_json import load_calibration
from rag_core.judging.infrastructure.ike_acl import summary_case
from rag_core.qa.domain.fact_check import CitedFactValidator
from rag_core.shared_kernel.errors import InvariantError
from tests.fixtures.ike.samples import NAMES, sample_issue, sample_referrals
from tests.fixtures.judge.samples import (
    FULL,
    OUT_OF_SCOPE_FA,
    qa_en,
    qa_fa,
    refusal_case,
)

pytestmark = [pytest.mark.judging, pytest.mark.judge]

ROOT = Path(__file__).resolve().parents[3]


def _judge(config: RuleJudgeConfig | None = None) -> RuleBasedJudge:
    return RuleBasedJudge(default_rubric(), CitedFactValidator(), config)


def _template_case(language: str):
    issue = sample_issue()
    graph = IkeService().build(issue, sample_referrals())
    facts = facts_lines(digest(issue, graph), NAMES)
    text = (
        IkeSummaryService(CitedFactValidator())
        .template(issue, graph, NAMES, language)
        .text
    )
    return summary_case(
        f"T-SUM-{language}",
        language,
        text,
        facts,
        NAMES,
        issue_id="AR-ISS-050",
        origin="ike-template",
    )


@pytest.mark.parametrize("case", [qa_fa(), qa_en()], ids=["fa", "en"])
def test_grounded_cited_answer_gets_full_marks(case) -> None:
    result = _judge().judge(case)
    assert result.scores == FULL, result.notes
    assert result.accepted and result.total == 20 and result.parse_mode == "rules"
    assert result.judge == "rule"


def test_invented_number_costs_grounding() -> None:
    case = qa_fa(
        "برای حادثهٔ اولویت ۱ پاسخ باید ظرف ۳۰ دقیقه و رفع موقت ظرف ۴ ساعت و جریمه ۷ درصد است [AR-SW-022 §4]."
    )
    result = _judge().judge(case)
    assert result.scores["grounding"] == 3
    assert "unsupported:7" in result.notes
    assert not result.accepted and "grounding 3<4" in result.outcome.reasons


def test_missing_key_fact_costs_correctness() -> None:
    case = qa_en(
        "A Priority 2 incident requires a response within 2 hours [AR-SW-022 §4]."
    )
    result = _judge().judge(case)
    assert (
        result.scores["correctness"] == 3 and result.scores["completeness"] == 2
    )  # 1/2 facts, half up
    assert "facts:1/2" in result.notes and not result.accepted


def test_answer_without_citation() -> None:
    result = _judge().judge(
        qa_en(
            "A Priority 2 incident requires a response within 2 hours and resolution "
            "within 16 business hours."
        )
    )
    assert (
        result.scores["citation"] == 0
        and "no_citation" in result.notes
        and not result.accepted
    )


def test_fabricated_citation_label() -> None:
    result = _judge().judge(
        qa_en(
            "A Priority 2 incident requires a response within 2 hours and resolution within 16 business hours "
            "[AR-SW-022 §4; AR-SW-099 §1]."
        )
    )
    assert result.scores["citation"] == 2
    assert "invalid_citation:AR-SW-099 §1" in result.notes and not result.accepted


def test_wrong_language_answer() -> None:
    result = _judge().judge(
        qa_fa(
            "For a Priority 1 incident the response is within 30 minutes and temporary "
            "restoration within 4 hours [AR-SW-022 §4]."
        )
    )
    assert (
        result.scores["clarity"] == 0
        and "wrong_language" in result.notes
        and not result.accepted
    )


def test_artifacts_and_length_cost_clarity() -> None:
    long_answer = (
        "<think>ok</think> " + qa_en().output + (" Extra filler sentence." * 70)
    )
    result = _judge().judge(qa_en(long_answer))
    assert result.scores["clarity"] == 1
    assert "too_long" in result.notes and "artifacts" in result.notes


def test_refusing_an_answerable_question() -> None:
    result = _judge().judge(
        qa_fa("INSUFFICIENT_CONTEXT اسناد کافی نیستند.", status="insufficient_context")
    )
    assert (
        result.scores["correctness"] == 0
        and "refused_although_answerable" in result.notes
    )
    assert not result.accepted


def test_answer_without_sources() -> None:
    result = _judge().judge(qa_en(sources=()))
    assert result.scores["grounding"] == 0 and "no_sources" in result.notes


def test_correct_out_of_scope_refusal_is_accepted() -> None:
    result = _judge().judge(
        refusal_case(OUT_OF_SCOPE_FA, "out_of_scope", escalation="N-CEO")
    )
    assert result.scores == FULL, result.notes
    assert result.accepted


def test_refusal_to_the_wrong_escalation_target() -> None:
    result = _judge().judge(
        refusal_case(OUT_OF_SCOPE_FA, "out_of_scope", escalation="N-ADM-HR")
    )
    assert result.scores["completeness"] == 1 and "escalation:N-ADM-HR" in result.notes
    assert not result.accepted


def test_not_found_where_out_of_scope_was_expected() -> None:
    text = "INSUFFICIENT_CONTEXT اسناد حوزهٔ این گره دربارهٔ این پرسش چیزی ندارند."
    result = _judge().judge(refusal_case(text, "insufficient_context"))
    assert result.scores["correctness"] == 2  # 40 % of 5, half up
    assert "status:insufficient_context!=out_of_scope" in result.notes
    assert not result.accepted


def test_not_found_refusal_is_accepted() -> None:
    text = "INSUFFICIENT_CONTEXT The documents in the scope of node N-CEO do not mention a pet policy."
    case = refusal_case(
        text, "insufficient_context", expected="not_found", language="en"
    )
    result = _judge().judge(case)
    assert result.scores == FULL, result.notes


def test_confident_answer_where_refusal_expected() -> None:
    case = refusal_case(
        "مرخصی بدون حقوق تا ۳۰ روز با تأیید معاون مجاز است [AR-HR-005 §4].", "answered"
    )
    result = _judge().judge(case)
    assert (
        result.total <= 3
        and "answered_without_scope_evidence" in result.notes
        and not result.accepted
    )


@pytest.mark.parametrize("language", ["fa", "en"])
def test_ike_template_summary_gets_full_marks(language: str) -> None:
    case = _template_case(language)
    assert case.expectation.items == (
        "AR-ISS-050/HW",
        "AR-ISS-050/WIN",
        "AR-ISS-050/WEB",
    )
    assert [i for i, _ in case.expectation.item_leads] == [
        "AR-ISS-050/HW",
        "AR-ISS-050/WIN",
    ]
    result = _judge().judge(case)
    assert result.scores == FULL, result.notes
    assert (
        result.accepted and "items:3/3" in result.notes and "gaps:4/4" in result.notes
    )


def test_summary_with_swapped_leads_is_rejected() -> None:
    case = _template_case("en")
    swapped = (
        case.output.replace("Saeed Akbari", "\x00")
        .replace("Roozbeh Mohseni", "Saeed Akbari")
        .replace("\x00", "Roozbeh Mohseni")
    )
    result = _judge().judge(case.mutated("swap", swapped))
    assert result.scores["correctness"] == 0
    assert "lead_missing:AR-ISS-050/HW" in result.notes and not result.accepted


def test_summary_missing_subissues_and_gaps() -> None:
    case = _template_case("en")
    first_two = "\n".join(case.output.splitlines()[:2])
    result = _judge().judge(case.mutated("short", first_two))
    # HW only: 1/3 sub-issue ids; of the 4 gap targets only AR-HW-015 (HW knowledge) is in the text.
    assert result.scores["citation"] == 1 and result.scores["completeness"] == 1
    assert "items:1/3" in result.notes and "gaps:1/4" in result.notes
    assert not result.accepted


def test_summary_with_invented_facts_and_empty_summary() -> None:
    case = _template_case("en")
    result = _judge().judge(
        case.mutated(
            "invent", case.output + "\nAR-ISS-050/HW needs 12 more days (AR-HW-099)."
        )
    )
    assert result.scores["grounding"] == 1 and not result.accepted
    empty = _judge().judge(case.mutated("empty", "  "))
    assert empty.total == 0 and empty.notes == ("empty",)


def test_summary_table_costs_clarity() -> None:
    case = _template_case("en")
    table = case.output + "\n| item | lead |\n| HW | x |"
    assert "table" in _judge().judge(case.mutated("table", table)).notes


def test_calibration_set_matches_gold_except_the_blind_spot() -> None:
    cases = load_calibration(ROOT / "data" / "judge" / "calibration-set.json")
    results = {c.case_id: _judge().judge(c) for c in cases}
    for case in cases:
        result = results[case.case_id]
        if "rule_blind_spot" in case.tags:
            assert result.accepted, (
                "the swapped-number case is the documented rule blind spot"
            )
            continue
        assert result.agrees_with_gold, (case.case_id, result.scores, result.notes)


def test_helpers() -> None:
    assert (
        first_item(
            "AR-ISS-050/WIN depends on AR-ISS-050/HW",
            ("AR-ISS-050/HW", "AR-ISS-050/WIN"),
        )
        == "AR-ISS-050/WIN"
    )
    assert first_item("no ids here", ("AR-ISS-050/HW",)) is None
    blocks = (SourceBlock("AR-SW-022 §4", "x", "AR-SW-022", 4, "fa"),)
    assert citation_valid(CitedRef("AR-SW-022 §4", "AR-SW-022", 4), blocks)
    assert citation_valid(CitedRef("AR-SW-022", "AR-SW-022"), blocks)
    assert not citation_valid(CitedRef("AR-SW-022 §5", "AR-SW-022", 5), blocks)
    assert not citation_valid(CitedRef("AR-SW-022 §4/en", "AR-SW-022", 4, "en"), blocks)


def test_rule_judge_needs_the_standard_criteria() -> None:
    other = Rubric("r", "1", (Criterion("style", 20, 10),))
    with pytest.raises(InvariantError):
        RuleBasedJudge(other, CitedFactValidator())
