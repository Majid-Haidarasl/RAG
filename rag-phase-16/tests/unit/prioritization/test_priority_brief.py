"""Phase 12 key-issue brief (template) and its Phase 10 rule-judge verdicts."""

import pytest

from rag_core.judging.application.services import judge_all
from rag_core.judging.domain.rubric import OutputKind, default_rubric
from rag_core.judging.domain.rule_judge import RuleBasedJudge
from rag_core.prioritization.domain.brief import MAX_RESEARCH, BriefGap, KeyIssueBrief, build_brief, num
from rag_core.prioritization.domain.scoring import PriorityScorer
from rag_core.prioritization.domain.unblocking import NextAction
from rag_core.prioritization.infrastructure.judging_acl import BriefJudge, brief_case, negative_brief_cases
from rag_core.qa.domain.fact_check import CitedFactValidator
from tests.fixtures.projects.samples import caps, shipped_like_signals, weights

pytestmark = [pytest.mark.prioritization]

GAPS = [
    BriefGap("KL:AR-ISS-024/WIN", "AR-ISS-024/WIN", "high", "Knowledge lack on AR-ISS-024/WIN: AR-SW-019",
             "کمبود دانش در AR-ISS-024/WIN: AR-SW-019", "AR-ISS-024"),
    BriefGap("DEP:AR-ISS-024/WIN", "AR-ISS-024/WIN", "high", "AR-ISS-024/WIN waits for AR-ISS-024/HW",
             "AR-ISS-024/WIN منتظر AR-ISS-024/HW است", "AR-ISS-024"),
    BriefGap("DEP:AR-ISS-024/LEG", "AR-ISS-024/LEG", "high", "AR-ISS-024/LEG waits for AR-ISS-024/HW",
             "AR-ISS-024/LEG منتظر AR-ISS-024/HW است", "AR-ISS-024"),
    BriefGap("KL:AR-ISS-033/UI", "AR-ISS-033/UI", "medium", "Not a key issue", "مسئله کلیدی نیست", "AR-ISS-033"),
]
RESEARCH = [
    BriefGap("RG:RES-PHOTO-TRIAGE", "RES-PHOTO-TRIAGE", "medium", "Photo triage of returned boards",
             "تریاژ تصویری بردهای برگشتی"),
    BriefGap("RG:RES-RETRIEVAL-EVAL", "RES-RETRIEVAL-EVAL", "medium", "Repair retrieval quality",
             "کیفیت بازیابی دانش تعمیر"),
    BriefGap("RG:RES-EXTRA", "RES-EXTRA", "low", "Extra", "اضافه"),
]
ACTIONS = {"AR-ISS-024": [NextAction("AR-ISS-024/HW", ("AR-ISS-024/LEG", "AR-ISS-024/WIN"))]}


def make(language: str) -> KeyIssueBrief:
    ranking = PriorityScorer(weights(), caps()).rank(shipped_like_signals())
    key = [r for r in ranking.ranked if r.key]
    return build_brief("1403-Q2", "1403-06-31", key, GAPS, RESEARCH, ACTIONS, language, tuple(ranking.order))


def rule_judge() -> RuleBasedJudge:
    return RuleBasedJudge(default_rubric(), CitedFactValidator())


def test_num_formats_the_same_way_everywhere() -> None:
    assert (num(12.0), num(11.25), num(80.75), num(62)) == ("12", "11.25", "80.75", "62")


def test_english_brief_content() -> None:
    b = make("en")
    assert b.items == ("AR-ISS-024", "AR-ISS-031", "AR-ISS-035")
    assert b.gaps == ("AR-ISS-024/WIN", "AR-ISS-024/LEG", "RES-PHOTO-TRIAGE", "RES-RETRIEVAL-EVAL")
    assert b.facts[0] == "Cycle 1403-Q2, reporting cutoff 1403-06-31."
    assert "1. AR-ISS-024 (Issue AR-ISS-024): score 80.75 of 100, status in_progress; main factors: urgency 12, " \
           "risk 12, priority 11.25. Progress 62%. Money at stake 1240 million toman." in b.text
    assert "Next action for AR-ISS-024: AR-ISS-024/HW, which unblocks AR-ISS-024/LEG, AR-ISS-024/WIN." in b.text
    assert "AR-ISS-033" not in b.text and "RES-EXTRA" not in b.text
    assert b.candidates[:3] == b.items and b.words > 50


def test_persian_brief_content() -> None:
    b = make("fa")
    assert b.facts[0] == "چرخه 1403-Q2، مقطع گزارش 1403-06-31."
    assert "امتیاز 80.75 از 100" in b.text and "فوریت 12، ریسک 12، اولویت 11.25" in b.text
    assert "پیشرفت 62٪" in b.text and "مبلغ در خطر 1240 میلیون تومان" in b.text
    assert "شکاف پژوهشی RES-PHOTO-TRIAGE" in b.text and "وضعیت بررسی‌شده" in b.text


def test_research_and_gap_limits() -> None:
    b = make("en")
    assert sum(1 for line in b.text.splitlines() if line.startswith("Research gap")) == MAX_RESEARCH
    assert sum(1 for line in b.text.splitlines() if line.startswith("Gap ")) == 3


def test_every_template_line_is_a_fact_or_built_from_facts() -> None:
    b = make("en")
    for line in b.text.splitlines()[1:]:
        if line.startswith(("Gap ", "Next action", "Research gap")):
            assert line in b.facts


def test_brief_case_fields() -> None:
    b = make("en")
    case = brief_case(b)
    assert case.case_id == "P12-brief-en" and case.kind is OutputKind.IKE_SUMMARY and case.node == "N-CEO"
    assert case.sources[0].text == "\n".join(b.facts) and case.output == b.text
    assert case.expectation.items == b.items and case.expectation.gaps == b.gaps
    assert brief_case(b, "x", origin="ai", suffix="ai").case_id == "P12-brief-en-ai"


@pytest.mark.parametrize("language", ["en", "fa"])
def test_rule_judge_accepts_the_template(language: str) -> None:
    judge = BriefJudge(rule_judge())
    result = judge.judge_brief(make(language))
    assert result.accepted, result.notes
    assert result.outcome.out_of == 20 and result.total >= 18
    assert judge.results == [result] and judge.name == "rule"


@pytest.mark.parametrize("language", ["en", "fa"])
def test_negative_briefs_are_rejected(language: str) -> None:
    cases = negative_brief_cases(make(language))
    results = judge_all(rule_judge(), cases)
    assert [c.origin for c in cases] == ["negative:wrong_number", "negative:fabricated_id", "negative:drop_items"]
    assert [r.accepted for r in results] == [False, False, False]
