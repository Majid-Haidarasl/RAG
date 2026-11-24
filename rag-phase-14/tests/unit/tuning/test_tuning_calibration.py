"""Phase 14 derived judge calibration: 14 reference answers + 14 broken answers from the gold set."""

from collections import Counter

import pytest

from rag_core.judging.application.services import judge_all
from rag_core.judging.domain.rubric import OutputKind
from rag_core.judging.domain.rule_judge import RuleBasedJudge
from rag_core.judging.infrastructure.calibration_json import load_calibration
from rag_core.judging.infrastructure.config import load_judge_settings
from rag_core.judging.infrastructure.prompt_yaml import load_rubric
from rag_core.qa.domain.fact_check import CitedFactValidator
from rag_core.shared_kernel.errors import InvariantError
from rag_core.tuning.infrastructure.judging_acl import (
    DECOY_DOCS,
    MUTATIONS,
    REFUSALS,
    answer_case,
    derive_calibration,
    expanded_calibration,
    fake_label,
    mutate,
    source_blocks,
    wrong_number,
)
from tests.fixtures.tuning.samples import (
    CALIBRATION,
    REPO,
    RUBRIC,
    answered_item,
    by_id,
    shipped_items,
)

pytestmark = [pytest.mark.tuning, pytest.mark.judging]


@pytest.fixture(scope="module")
def derived():  # noqa: ANN201
    return derive_calibration(shipped_items())


@pytest.fixture(scope="module")
def rule_judge() -> RuleBasedJudge:
    jset = load_judge_settings(REPO / "config" / "judge.yaml")
    return RuleBasedJudge(load_rubric(RUBRIC), CitedFactValidator(), jset.rules)


def test_source_blocks_follow_the_labels() -> None:
    blocks = source_blocks(by_id("GQ-P06-en"))
    assert [b.label for b in blocks] == ["AR-ISS-024 §1", "AR-ISS-024 §2"]
    assert [b.order for b in blocks] == [1, 2] and all(
        b.language == "en" for b in blocks
    )


def test_answer_case_fields() -> None:
    item = answered_item("en")
    case = answer_case(
        item,
        item.reference_answer,
        case_id="C1",
        gold="accept",
        origin="calibration-derived",
    )
    assert (
        case.kind is OutputKind.QA_ANSWER
        and case.expectation.facts == item.expected_facts
    )
    assert (
        case.node == "N-SW-SUP"
        and case.status == "answered"
        and case.sources[0].document_id == "AR-SW-022"
    )


def test_wrong_number_changes_the_last_number_only() -> None:
    out = wrong_number(
        "Within 30 minutes and 4 hours [AR-SW-022 §1].", ["30 minutes, 4 hours"]
    )
    assert out == "Within 30 minutes and 11 hours [AR-SW-022 §1]."


def test_wrong_number_keeps_persian_digits_and_skips_source_numbers() -> None:
    out = wrong_number(
        "پاسخ ظرف ۳۰ دقیقه و رفع موقت ۴ ساعت [AR-SW-022 §1].",
        ["۳۰ دقیقه، ۴ ساعت، ۱۱ ساعت"],
    )
    assert out == "پاسخ ظرف ۳۰ دقیقه و رفع موقت ۱۵ ساعت [AR-SW-022 §1]."


def test_wrong_number_thousands_and_ids() -> None:
    out = wrong_number(
        "The fine is 2,000 rials for AR-LEG-009 [AR-LEG-009 §1].", ["2,000"]
    )
    assert out == "The fine is 2,007 rials for AR-LEG-009 [AR-LEG-009 §1]."
    assert wrong_number("No numbers here [AR-SW-022 §1].", []) is None


def test_fake_label_points_at_a_decoy() -> None:
    out = fake_label("A [AR-SW-022 §1]. B [AR-SW-022 §2].", ["AR-SW-022"])
    assert out == "A [AR-HR-011 §1]. B [AR-HR-011 §2]."
    assert fake_label("A [AR-HR-011 §1].", ["AR-HR-011"]) == "A [AR-HR-004 §1]."
    assert fake_label("no label", ["AR-SW-022"]) is None and DECOY_DOCS == (
        "AR-HR-011",
        "AR-HR-004",
    )


def test_mutate_each_kind() -> None:
    fa, en = answered_item("fa"), answered_item("en")
    assert mutate(en, "drop_fact", fa) == (en.partial_answer, "answered")
    assert mutate(en, "wrong_language", fa) == (fa.reference_answer, "answered")
    assert mutate(en, "refuse_answerable", fa) == (
        REFUSALS["en"],
        "insufficient_context",
    )
    assert mutate(en, "wrong_language", None) is None
    assert (
        mutate(en.__class__(**{**en.__dict__, "partial_answer": ""}), "drop_fact", fa)
        is None
    )
    with pytest.raises(InvariantError, match="unknown mutation"):
        mutate(en, "shout", fa)


def test_derived_size_and_ids(derived) -> None:  # noqa: ANN001
    assert len(derived) == 28
    ok = [d for d in derived if not d.mutation]
    bad = [d for d in derived if d.mutation]
    assert len(ok) == len(bad) == 14
    assert all(d.case.gold == "accept" and d.case.case_id.endswith("-ok") for d in ok)
    assert all(
        d.case.gold == "reject" and d.case.origin == f"negative:{d.mutation}"
        for d in bad
    )
    assert len({d.case.case_id for d in derived}) == 28 and all(
        "derived" in d.case.tags for d in derived
    )


def test_every_mutation_kind_is_used(derived) -> None:  # noqa: ANN001
    counts = Counter(d.mutation for d in derived if d.mutation)
    assert set(counts) == set(MUTATIONS) and min(counts.values()) >= 2


def test_languages_alternate_within_a_pair(derived) -> None:  # noqa: ANN001
    by_pair: dict[str, set[str]] = {}
    for d in derived:
        by_pair.setdefault(d.case.case_id.split("-")[1], set()).add(d.case.language)
    assert (
        all(langs == {"fa", "en"} for langs in by_pair.values()) and len(by_pair) == 14
    )
    ok_langs = Counter(d.case.language for d in derived if not d.mutation)
    assert ok_langs == Counter({"fa": 7, "en": 7})


def test_refusal_pairs_are_not_used(derived) -> None:  # noqa: ANN001
    assert not any(
        d.case.case_id.startswith(("CAL14-P09", "CAL14-P10")) for d in derived
    )


def test_rule_judge_accepts_every_reference_answer(derived, rule_judge) -> None:  # noqa: ANN001
    results = judge_all(rule_judge, [d.case for d in derived if not d.mutation])
    assert all(r.accepted for r in results), [
        (r.case_id, r.total, r.notes) for r in results if not r.accepted
    ]


def test_rule_judge_rejects_every_broken_answer(derived, rule_judge) -> None:  # noqa: ANN001
    results = judge_all(rule_judge, [d.case for d in derived if d.mutation])
    assert not any(r.accepted for r in results), [
        r.case_id for r in results if r.accepted
    ]


def test_expanded_set_has_42_cases() -> None:
    cases = expanded_calibration(load_calibration(CALIBRATION), shipped_items())
    assert len(cases) == 42 and sum(1 for c in cases if c.gold == "reject") == 6 + 14


def test_expanded_set_rejects_duplicate_ids() -> None:
    base = load_calibration(CALIBRATION)
    with pytest.raises(InvariantError, match="duplicate"):
        expanded_calibration([*base, base[0]], [])
