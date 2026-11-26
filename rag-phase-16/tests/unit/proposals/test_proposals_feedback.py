"""Phase 13 automated bidder feedback: template lines, judged like a summary."""

import pytest

from rag_core.judging.application.services import judge_all
from rag_core.judging.domain.rubric import default_rubric
from rag_core.judging.domain.rule_judge import RuleBasedJudge
from rag_core.proposals.domain.evaluation import evaluate
from rag_core.proposals.domain.feedback import build_feedback
from rag_core.qa.domain.fact_check import CitedFactValidator
from rag_core.rfp.infrastructure.judging_acl import (
    feedback_task,
    negative_cases,
    summary_case,
)
from tests.fixtures.rfp.samples import shipped_blueprint, shipped_registry

pytestmark = [pytest.mark.proposals]


def fb(pid: str, lang: str):
    bp, reg = shipped_blueprint(), shipped_registry()
    return build_feedback(bp, reg, evaluate(bp, reg), pid, lang)


def case(pid: str, lang: str):
    f = fb(pid, lang)
    return summary_case(
        f"P13-fb-{pid}-{lang}",
        lang,
        feedback_task(pid, lang),
        f.text,
        f.facts,
        f.items,
        f.gaps,
        origin="feedback-template",
    ), f


def test_english_feedback_for_the_runner_up() -> None:
    f = fb("PRP-B", "en")
    assert (
        f.facts[0]
        == "Feedback on proposal PRP-B (B, Novin Gozaresh Pars) to RFP AR-RFP-1403-07, version 1.0."
    )
    assert f.facts[1] == (
        "Weighted score 75.2 of 100 = CRT-TECH (Technical) 68 × 60% = 40.8; CRT-FIN (Financial) "
        "86 × 40% = 34.4; rank 2 of 2."
    )
    assert (
        f.facts[2]
        == "Selected proposal PRP-A (Dadeh Pardaz Shafagh) with 78.8; gap 3.6 points."
    )
    assert f.facts[3] == (
        "Price 240 million toman and duration 5 weeks; lowest price 240 million toman (PRP-B) and "
        "shortest duration 5 weeks (PRP-B)."
    )
    assert any(x.startswith("Recorded feedback: The shorter duration") for x in f.facts)
    assert (
        f.facts[-1]
        == "This result is recorded under AR-ISS-024/WEB, AR-ISS-024, AR-ISS-035 in node N-SW."
    )


def test_english_feedback_for_the_winner() -> None:
    f = fb("PRP-A", "en")
    assert "This proposal was selected; lead over the next one 3.6 points." in f.facts
    assert not any(
        x.startswith("Recorded feedback") for x in f.facts
    )  # nothing recorded for A
    assert any("assumptions behind the seven weeks" in x for x in f.facts)


def test_persian_feedback() -> None:
    f = fb("PRP-B", "fa")
    assert f.facts[0].startswith("بازخورد پیشنهاد PRP-B (ب، ")
    assert "امتیاز وزنی 75.2 از 100" in f.facts[1] and "رتبه 2 از 2" in f.facts[1]
    assert "60٪" in f.facts[1] and "میلیون تومان" in f.facts[3]


def test_items_gaps_and_headings() -> None:
    f = fb("PRP-B", "en")
    assert f.items == ("AR-RFP-1403-07", "PRP-B") and f.gaps == (
        "AR-ISS-024/WEB",
        "AR-ISS-024",
        "AR-ISS-035",
    )
    headings = [line for line in f.text.splitlines() if line not in f.facts]
    assert headings == [
        "Result:",
        "Comparison:",
        "Evaluator notes:",
        "Knowledge record:",
    ]


@pytest.mark.parametrize("pid", ["PRP-A", "PRP-B"])
@pytest.mark.parametrize("lang", ["fa", "en"])
def test_template_feedback_is_accepted_and_broken_copies_rejected(
    pid: str, lang: str
) -> None:
    judge = RuleBasedJudge(default_rubric(), CitedFactValidator())
    c, f = case(pid, lang)
    r = judge_all(judge, [c])[0]
    assert r.accepted and r.total == 20, r.notes
    assert all(not x.accepted for x in judge_all(judge, negative_cases(c, f.items)))


def test_unknown_proposal() -> None:
    with pytest.raises(KeyError):
        fb("PRP-Z", "en")
