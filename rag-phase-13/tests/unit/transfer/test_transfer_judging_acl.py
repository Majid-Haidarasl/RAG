"""Package → Phase 10 judge case; rule judge, scripted LLM judge and the combined judge."""

from pathlib import Path

import pytest

from rag_core.judging.application.services import LlmJudge, judge_all
from rag_core.judging.domain.rubric import OutputKind, default_rubric
from rag_core.judging.domain.rule_judge import RuleBasedJudge
from rag_core.judging.infrastructure.prompt_yaml import load_judge_prompts
from rag_core.qa.domain.fact_check import CitedFactValidator
from rag_core.transfer.infrastructure.judging_acl import CaseJudgeAdapter, CombinedPackageJudge, package_case
from tests.fixtures.judge.samples import ScriptedJudgeModel, reply
from tests.fixtures.transfer.samples import draft_for, team_hw

pytestmark = [pytest.mark.transfer, pytest.mark.transfer_pkg]

ROOT = Path(__file__).resolve().parents[3]
PROMPTS = load_judge_prompts(ROOT / "config" / "prompts" / "judge")


def test_package_case_fields() -> None:
    d = draft_for(team_hw(), "N-HW", 2)
    case = package_case(d, "fa")
    assert case.case_id == "P11-N-HW-REP-fa" and case.kind is OutputKind.IKE_SUMMARY
    assert case.output == d.text("fa") and case.node == "N-HW-REP" and case.origin == "transfer-template"
    assert case.sources[0].text == "\n".join(d.facts)
    assert case.expectation.items == ("AR-ISS-024/HW", "AR-ISS-034")
    assert case.expectation.gaps == ("AR-HW-013",)
    assert "lead executor" in case.task


def test_rule_adapter_scores_template_and_records_result() -> None:
    adapter = CaseJudgeAdapter(RuleBasedJudge(default_rubric(), CitedFactValidator()))
    verdict = adapter.judge_package(draft_for(team_hw(), "N-HW", 2), "en")[0]
    assert verdict.judge == "rule" and verdict.accepted and verdict.out_of == 20
    assert adapter.results[0].origin == "transfer-template"


def test_negative_copies_are_rejected_by_the_rule_judge() -> None:
    d = draft_for(team_hw(), "N-HW", 2)
    base = package_case(d, "en")
    text = d.text("en")
    cases = [base.mutated("wrong_number", text + " Penalty 777 million toman."),
             base.mutated("fabricated_id", text + " See AR-ISS-099."),
             base.mutated("drop_items", "\n".join(line for line in text.splitlines()
                                                   if not any(i in line for i in d.rendered.expected_items)))]
    results = judge_all(RuleBasedJudge(default_rubric(), CitedFactValidator()), cases)
    assert [r.accepted for r in results] == [False, False, False]
    assert {r.origin for r in results} == {"negative:wrong_number", "negative:fabricated_id", "negative:drop_items"}


def test_combined_judge_needs_both() -> None:
    d = draft_for(team_hw(), "N-HW", 2)
    rule = CaseJudgeAdapter(RuleBasedJudge(default_rubric(), CitedFactValidator()))
    low = {"grounding": 2, "correctness": 2, "citation": 2, "completeness": 1, "clarity": 1}
    llm = CaseJudgeAdapter(LlmJudge(default_rubric(), PROMPTS, ScriptedJudgeModel([reply(low)]), name="llm:fake"))
    combined = CombinedPackageJudge(rule, llm)
    verdicts = combined.judge_package(d, "en")
    assert [v.judge for v in verdicts] == ["rule", "llm:fake"]
    assert [v.accepted for v in verdicts] == [True, False]
    assert combined.name == "rule+llm:fake"


def test_ai_text_is_marked_as_ai_origin() -> None:
    adapter = CaseJudgeAdapter(RuleBasedJudge(default_rubric(), CitedFactValidator()))
    v = adapter.judge_package(draft_for(team_hw(), "N-HW", 2), "en", "Nothing useful.")[0]
    assert not v.accepted
    assert adapter.results[0].origin == "transfer-ai"
