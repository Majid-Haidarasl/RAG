"""Phase 13 RFP text through the Phase 10 rule judge: template accepted, broken copies rejected."""

import pytest

from rag_core.judging.application.services import judge_all
from rag_core.judging.domain.rubric import OutputKind, default_rubric
from rag_core.judging.domain.rule_judge import RuleBasedJudge, RuleJudgeConfig
from rag_core.qa.domain.fact_check import CitedFactValidator
from rag_core.rfp.domain.generator import build_rfp, select_candidates
from rag_core.rfp.infrastructure.judging_acl import feedback_task, negative_cases, rfp_task, summary_case
from tests.fixtures.rfp.samples import CYCLE, TARGETS, gap_views, item_view, key_views, shipped_blueprint

pytestmark = [pytest.mark.rfp_gen]


def judge(max_chars: int = 6000) -> RuleBasedJudge:
    return RuleBasedJudge(default_rubric(), CitedFactValidator(), RuleJudgeConfig(max_summary_chars=max_chars))


def case(language: str):  # noqa: ANN201
    bp = shipped_blueprint()
    cands = select_candidates(key_views(), [bp], ("procurement",), TARGETS)
    d = build_rfp(bp, cands, {k.issue_id: k for k in key_views()}, gap_views(), language, CYCLE, item_view())
    return summary_case(f"P13-rfp-{language}", language, rfp_task(d.rfp_id, language), d.text, d.facts, d.items,
                        d.gaps), d


@pytest.mark.parametrize("language", ["fa", "en"])
def test_template_rfp_scores_full_marks(language: str) -> None:
    c, _ = case(language)
    r = judge_all(judge(), [c])[0]
    assert r.accepted and r.total == 20, r.notes


def test_summary_limit_costs_one_clarity_point_only() -> None:
    c, _ = case("en")
    r = judge_all(judge(3000), [c])[0]
    assert r.accepted and r.total == 19 and "too_long" in r.notes


@pytest.mark.parametrize("language", ["fa", "en"])
def test_broken_copies_are_rejected(language: str) -> None:
    c, d = case(language)
    negatives = negative_cases(c, d.items)
    assert [n.origin for n in negatives] == ["negative:wrong_number", "negative:fabricated_id", "negative:drop_items"]
    assert all(not r.accepted for r in judge_all(judge(), negatives))
    assert not any(i in negatives[2].output for i in d.items)


def test_case_shape() -> None:
    c, d = case("en")
    assert c.kind is OutputKind.IKE_SUMMARY and c.language == "en" and c.node == "N-SW"
    assert c.sources[0].text == "\n".join(d.facts)
    assert c.expectation.items == d.items and c.expectation.gaps == d.gaps


def test_task_texts_name_the_subject() -> None:
    assert "AR-RFP-1403-07" in rfp_task("AR-RFP-1403-07", "fa") and "Persian" in rfp_task("AR-RFP-1403-07", "fa")
    assert "PRP-B" in feedback_task("PRP-B", "en") and "English" in feedback_task("PRP-B", "en")
