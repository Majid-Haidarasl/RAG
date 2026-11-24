"""Phase 14 shipped gold set eval/datasets/armanrayan-qa.jsonl (Persian + English)."""

import pytest

from rag_core.judging.domain.text import language_matches
from rag_core.qa.application.evaluation import facts_found, load_samples
from rag_core.tuning.domain.gold import (
    cited_labels,
    pairs,
    phase8_coverage,
    validate_gold,
)
from tests.fixtures.tuning.samples import REPO, by_id, shipped_items

pytestmark = [pytest.mark.tuning, pytest.mark.eval_gold]


def test_size_and_languages() -> None:
    items = shipped_items()
    assert len(items) == 32 and len(pairs(items)) == 16
    assert (
        sum(1 for i in items if i.language == "fa")
        == sum(1 for i in items if i.language == "en")
        == 16
    )
    assert len({i.id for i in items}) == 32


def test_no_validation_problems() -> None:
    problems = validate_gold(shipped_items(), facts_found, language_matches)
    assert problems == [], [str(p) for p in problems]


def test_status_mix() -> None:
    statuses = [i.expected_status for i in shipped_items()]
    assert (
        statuses.count("answered") == 28
        and statuses.count("out_of_scope") == 2
        and statuses.count("not_found") == 2
    )


def test_all_phase8_samples_are_covered() -> None:
    ids = [s.id for s in load_samples(REPO / "data" / "rag" / "sample-questions.json")]
    assert phase8_coverage(shipped_items(), ids) == (10, 10, [])


def test_phase8_questions_keep_their_node_and_documents() -> None:
    samples = {
        s.id: s for s in load_samples(REPO / "data" / "rag" / "sample-questions.json")
    }
    for item in shipped_items():
        if item.phase8_id:
            s = samples[item.phase8_id]
            assert item.node == s.node and item.expected_status == s.expected_status, (
                item.id
            )
            assert (
                set(s.expected_docs) <= set(item.expected_docs) or not s.expected_docs
            ), item.id


def test_q06_lists_all_four_causes() -> None:
    for lang in ("fa", "en"):
        item = by_id(f"GQ-P06-{lang}")
        assert (
            item.detail == "list"
            and len(item.expected_facts) == 4
            and len(item.evidence) == 2
        )
        assert facts_found(item.reference_answer, item.expected_facts) == (4, 4)
        assert facts_found(item.partial_answer, item.expected_facts)[0] <= 2


def test_out_of_scope_items_escalate() -> None:
    for lang in ("fa", "en"):
        item = by_id(f"GQ-P09-{lang}")
        assert (
            item.expected_outside_docs == ("AR-HR-005",)
            and item.expected_escalation == "N-CEO"
        )
        assert item.reference_answer.startswith("INSUFFICIENT_CONTEXT")


def test_reference_labels_point_at_evidence() -> None:
    for item in shipped_items():
        if item.answered:
            valid = {(e.document_id, n) for n, e in enumerate(item.evidence, 1)}
            labels = cited_labels(item.reference_answer)
            assert labels and all(lab in valid for lab in labels), item.id


def test_partial_answers_keep_at_most_half_of_the_facts() -> None:
    for item in shipped_items():
        if item.answered and len(item.expected_facts) >= 2:
            hit, total = facts_found(item.partial_answer, item.expected_facts)
            assert 2 * hit <= total, item.id


def test_new_pairs_have_a_phase14_origin() -> None:
    new = {
        p
        for p, by in pairs(shipped_items()).items()
        if all(i.origin == "phase14" for i in by.values())
    }
    assert new == {"P11", "P12", "P13", "P14", "P15", "P16"}


def test_required_sub_issue_ids_in_the_reference() -> None:
    for lang in ("fa", "en"):
        ref = by_id(f"GQ-P15-{lang}").reference_answer
        assert "AR-SW-019" in ref and "AR-ISS-024/WIN" in ref
