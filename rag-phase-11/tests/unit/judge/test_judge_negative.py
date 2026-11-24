"""Phase 10 negative controls: broken copies of good outputs that every judge must reject."""

import pytest

from rag_core.ike.application.services import IkeService, IkeSummaryService
from rag_core.ike.domain.summary import digest, facts_lines
from rag_core.judging.domain.cases import Expectation
from rag_core.judging.domain.negative import (
    FAKE_LABEL,
    REFUSAL_TEXT,
    NegativeKind,
    answer_unanswerable,
    drop_items,
    fabricated_citation,
    negative_controls,
    off_topic,
    refuse_answerable,
    wrong_lead,
    wrong_number,
)
from rag_core.judging.domain.rubric import default_rubric
from rag_core.judging.domain.rule_judge import RuleBasedJudge
from rag_core.judging.infrastructure.ike_acl import summary_case
from rag_core.qa.domain.fact_check import CitedFactValidator
from tests.fixtures.ike.samples import NAMES, sample_issue, sample_referrals
from tests.fixtures.judge.samples import (
    HR_FA,
    OUT_OF_SCOPE_FA,
    qa_en,
    qa_fa,
    refusal_case,
)

pytestmark = [pytest.mark.judging, pytest.mark.judge]


def _judge() -> RuleBasedJudge:
    return RuleBasedJudge(default_rubric(), CitedFactValidator())


def _summary(language: str):  # noqa: ANN202
    issue = sample_issue()
    graph = IkeService().build(issue, sample_referrals())
    facts = facts_lines(digest(issue, graph), NAMES)
    text = (
        IkeSummaryService(CitedFactValidator())
        .template(issue, graph, NAMES, language)
        .text
    )
    return summary_case(
        f"S-{language}",
        language,
        text,
        facts,
        NAMES,
        issue_id="AR-ISS-050",
        origin="ike-template",
    )


def _hr_case():  # noqa: ANN202
    return qa_fa(
        "سقف مرخصی ساعتی ۴ ساعت در روز و ۱۶ ساعت در ماه است [AR-HR-005 §5].",
        case_id="T-HR",
        task="سقف مرخصی ساعتی چقدر است؟",
        sources=(HR_FA,),
        expectation=Expectation(
            status="answered", facts=(("4", "چهار"), ("16", "شانزده"))
        ),
    )


def test_wrong_number_changes_numbers_but_not_labels_or_ids() -> None:
    case = qa_en(
        "Contract AR-CNT-1402-118 at node N-SW-SUP: response within 2 hours and resolution within 16 "
        "business hours [AR-SW-022 §4]."
    )
    neg = wrong_number(case)
    assert neg is not None
    assert "27 hours" in neg.output and "167 business" in neg.output
    assert (
        "AR-CNT-1402-118" in neg.output
        and "[AR-SW-022 §4]" in neg.output
        and "N-SW-SUP" in neg.output
    )
    assert (
        neg.case_id == "T-EN~wrong_number"
        and neg.origin == "negative:wrong_number"
        and neg.gold == "reject"
    )
    assert neg.is_negative


def test_wrong_number_handles_persian_digits_and_skips_texts_without_numbers() -> None:
    neg = wrong_number(qa_fa())
    assert neg is not None and "307" in neg.output and "47" in neg.output
    assert wrong_number(qa_en("No numbers at all here [AR-SW-022 §4].")) is None


def test_fabricated_citation() -> None:
    neg = fabricated_citation(qa_en())
    assert (
        neg is not None
        and f"[{FAKE_LABEL}]" in neg.output
        and "AR-SW-022" not in neg.output
    )
    assert fabricated_citation(qa_en("No label here.")) is None


def test_off_topic_takes_another_answer_with_other_documents() -> None:
    sla = qa_fa()
    hr = _hr_case()
    neg = off_topic(sla, [sla, hr])
    assert neg is not None and neg.output == hr.output and neg.sources == sla.sources
    assert off_topic(sla, [sla, qa_en()]) is None  # other language only


def test_refuse_answerable_and_answer_unanswerable() -> None:
    neg = refuse_answerable(qa_en())
    assert (
        neg is not None
        and neg.output == REFUSAL_TEXT["en"]
        and neg.status == "insufficient_context"
    )
    ref = refusal_case(OUT_OF_SCOPE_FA, "out_of_scope", escalation="N-CEO")
    assert refuse_answerable(ref) is None
    neg2 = answer_unanswerable(ref)
    assert (
        neg2 is not None
        and neg2.status == "answered"
        and neg2.escalation == ""
        and "[" in neg2.output
    )
    assert answer_unanswerable(qa_en()) is None


def test_drop_items_keeps_only_the_first_subissue() -> None:
    case = _summary("en")
    neg = drop_items(case)
    assert neg is not None and "AR-ISS-050/HW" in neg.output
    assert "AR-ISS-050/WIN" not in neg.output and "AR-ISS-050/WEB" not in neg.output


def test_wrong_lead_rotates_names() -> None:
    case = _summary("fa")
    neg = wrong_lead(case)
    assert neg is not None and neg.output != case.output
    hw_line = next(
        line for line in neg.output.splitlines() if line.startswith("- AR-ISS-050/HW")
    )
    assert (
        NAMES["EX-ROOZBEH-MOHSENI"][1] in hw_line
        and NAMES["EX-SAEED-AKBARI"][1] not in hw_line
    )


def test_summary_mutations_need_enough_material() -> None:
    case = _summary("en")
    short = case.mutated("one", "AR-ISS-050/HW is led by Saeed Akbari.")
    assert drop_items(short) is None and wrong_lead(short) is None


def test_negative_controls_one_per_positive_with_rotation() -> None:
    cases = [
        qa_fa(),
        qa_en(),
        _hr_case(),
        refusal_case(OUT_OF_SCOPE_FA, "out_of_scope", escalation="N-CEO"),
        _summary("fa"),
        _summary("en"),
    ]
    negs = negative_controls(cases)
    kinds = [n.origin.split(":", 1)[1] for n in negs]
    assert kinds == [
        NegativeKind.WRONG_NUMBER,
        NegativeKind.FABRICATED_CITATION,
        NegativeKind.OFF_TOPIC,
        NegativeKind.ANSWER_UNANSWERABLE,
        NegativeKind.DROP_ITEMS,
        NegativeKind.WRONG_LEAD,
    ]
    assert all(n.gold == "reject" for n in negs)
    assert negative_controls(negs) == []  # negatives are never mutated again


def test_rule_judge_rejects_every_negative_control() -> None:
    cases = [
        qa_fa(),
        qa_en(),
        _hr_case(),
        refusal_case(OUT_OF_SCOPE_FA, "out_of_scope", escalation="N-CEO"),
        _summary("fa"),
        _summary("en"),
    ]
    judge = _judge()
    assert all(judge.judge(c).accepted for c in cases)
    for neg in negative_controls(cases):
        result = judge.judge(neg)
        assert not result.accepted, (neg.case_id, result.scores, result.notes)
        assert result.agrees_with_gold is True
