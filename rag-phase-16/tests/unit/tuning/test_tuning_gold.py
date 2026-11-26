"""Phase 14 gold items: invariants, labels, pairs and every validation code."""

from dataclasses import replace

import pytest

from rag_core.shared_kernel.errors import InvariantError
from rag_core.tuning.domain.gold import (
    Evidence,
    cited_labels,
    pairs,
    phase8_coverage,
    validate_gold,
)
from tests.fixtures.tuning.samples import (
    answered_item,
    refusal_item,
    simple_found,
    simple_language,
)

pytestmark = [pytest.mark.tuning, pytest.mark.eval_gold]


def codes(items) -> set[str]:
    return {p.code for p in validate_gold(items, simple_found, simple_language)}


def test_a_complete_pair_has_no_problems() -> None:
    assert (
        validate_gold(
            [answered_item("fa"), answered_item("en")], simple_found, simple_language
        )
        == []
    )


def test_refusal_pair_has_no_problems() -> None:
    assert (
        validate_gold(
            [refusal_item("fa"), refusal_item("en")], simple_found, simple_language
        )
        == []
    )


def test_item_invariants() -> None:
    with pytest.raises(InvariantError, match="language"):
        answered_item(language="en").__class__(
            **{**answered_item().__dict__, "language": "de"}
        )
    with pytest.raises(InvariantError, match="expected_status"):
        replace(answered_item(), expected_status="maybe")
    with pytest.raises(InvariantError, match="detail"):
        replace(answered_item(), detail="essay")
    with pytest.raises(InvariantError, match="question and node"):
        replace(answered_item(), question=" ")
    with pytest.raises(InvariantError, match="id and a pair"):
        replace(answered_item(), pair="")


def test_evidence_invariants() -> None:
    with pytest.raises(InvariantError):
        Evidence("AR-SW-022", "en", " ")
    with pytest.raises(InvariantError, match="fa or en"):
        Evidence("AR-SW-022", "de", "text")


def test_labels_and_properties() -> None:
    item = replace(
        answered_item(),
        evidence=(Evidence("AR-SW-022", "en", "a"), Evidence("AR-HR-005", "en", "b")),
    )
    assert item.labels == ("AR-SW-022 §1", "AR-HR-005 §2")
    assert item.quote_text == "a\nb" and item.answered and item.phase8_id == "Q01"
    assert replace(item, origin="phase14").phase8_id == ""


def test_cited_labels() -> None:
    assert cited_labels("x [AR-SW-022 §1]. y [AR-SW-022 §2; AR-HR-005 §1]") == [
        ("AR-SW-022", 1),
        ("AR-SW-022", 2),
        ("AR-HR-005", 1),
    ]
    assert cited_labels("x [see the policy]") == [None]
    assert cited_labels("no labels") == []


def test_pairs_groups_by_pair_and_language() -> None:
    grouped = pairs([answered_item("en"), refusal_item("fa"), answered_item("fa")])
    assert list(grouped) == ["P01", "P09"] and set(grouped["P01"]) == {"fa", "en"}


def test_duplicate_id() -> None:
    assert "duplicate_id" in codes(
        [answered_item("en"), answered_item("en"), answered_item("fa")]
    )


def test_question_in_the_wrong_language() -> None:
    assert "wrong_language" in codes(
        [answered_item("en", question="چند روز؟"), answered_item("fa")]
    )


def test_missing_docs_facts_and_evidence() -> None:
    found = codes(
        [
            answered_item("en", expected_docs=(), expected_facts=(), evidence=()),
            answered_item("fa"),
        ]
    )
    assert {"missing_docs", "missing_facts", "missing_evidence"} <= found


def test_evidence_language_and_document() -> None:
    bad = (Evidence("AR-HR-005", "fa", "۳۰ و ۴"),)
    found = codes([answered_item("en", evidence=bad), answered_item("fa")])
    assert {"evidence_language", "evidence_document"} <= found


def test_fact_not_in_evidence() -> None:
    found = codes(
        [
            answered_item(
                "en",
                evidence=(Evidence("AR-SW-022", "en", "Response within 30 minutes."),),
            ),
            answered_item("fa"),
        ]
    )
    assert "fact_not_in_evidence" in found


def test_reference_missing_fact() -> None:
    assert "reference_missing_fact" in codes(
        [
            answered_item("en", reference_answer="Within 30 minutes [AR-SW-022 §1]."),
            answered_item("fa"),
        ]
    )


def test_reference_labels() -> None:
    no_label = codes(
        [
            answered_item("en", reference_answer="Within 30 minutes and 4 hours."),
            answered_item("fa"),
        ]
    )
    wrong = codes(
        [
            answered_item(
                "en", reference_answer="Within 30 minutes and 4 hours [AR-SW-022 §2]."
            ),
            answered_item("fa"),
        ]
    )
    other_doc = codes(
        [
            answered_item(
                "en", reference_answer="Within 30 minutes and 4 hours [AR-HR-005 §1]."
            ),
            answered_item("fa"),
        ]
    )
    assert (
        "reference_label" in no_label
        and "reference_label" in wrong
        and "reference_label" in other_doc
    )


def test_reference_in_the_wrong_language() -> None:
    found = codes(
        [
            answered_item(
                "fa", reference_answer="Within ۳۰ minutes and ۴ hours [AR-SW-022 §1]."
            ),
            answered_item("en"),
        ]
    )
    assert "wrong_language" in found


def test_partial_answer_rules() -> None:
    assert "partial_missing" in codes(
        [answered_item("en", partial_answer=""), answered_item("fa")]
    )
    assert "partial_too_complete" in codes(
        [
            answered_item("en", partial_answer="30 and 4 [AR-SW-022 §1]."),
            answered_item("fa"),
        ]
    )
    assert "partial_label" in codes(
        [answered_item("en", partial_answer="Within 30 minutes."), answered_item("fa")]
    )


def test_single_fact_items_need_no_partial_answer() -> None:
    one = answered_item("en", expected_facts=(("30",),), partial_answer="")
    assert "partial_missing" not in codes(
        [one, answered_item("fa", expected_facts=(("۳۰",),), partial_answer="")]
    )


def test_refusal_rules() -> None:
    assert "refusal_with_facts" in codes(
        [refusal_item("en", expected_facts=(("5",),)), refusal_item("fa")]
    )
    assert "refusal_reference" in codes(
        [refusal_item("en", reference_answer="Five days."), refusal_item("fa")]
    )
    assert "escalation_missing" in codes(
        [refusal_item("en", expected_escalation=""), refusal_item("fa")]
    )
    assert "refusal_detail" in codes(
        [refusal_item("en", detail="short"), refusal_item("fa")]
    )


def test_not_found_needs_no_escalation() -> None:
    items = [
        refusal_item(
            lang,
            expected_status="not_found",
            expected_outside_docs=(),
            expected_escalation="",
        )
        for lang in ("fa", "en")
    ]
    assert codes(items) == set()


def test_pair_incomplete_and_mismatch() -> None:
    assert "pair_incomplete" in codes([answered_item("en")])
    mismatch = validate_gold(
        [answered_item("fa"), answered_item("en", detail="list")],
        simple_found,
        simple_language,
    )
    assert any(p.code == "pair_mismatch" and p.detail == "detail" for p in mismatch)


def test_phase8_coverage() -> None:
    items = [
        answered_item("en"),
        answered_item("fa"),
        refusal_item("en"),
        refusal_item("fa"),
    ]
    assert phase8_coverage(items, ["Q01", "Q09", "Q10"]) == (2, 3, ["Q10"])
    assert phase8_coverage(items, []) == (0, 0, [])
