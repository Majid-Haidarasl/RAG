"""Detail-level rules per receiving layer (AR-TRN-026)."""

from dataclasses import replace

import pytest

from rag_core.shared_kernel.errors import InvariantError, NotFoundError
from rag_core.transfer.domain.levels import DEFAULT_RULES, AggregationMode, RuleBook
from rag_core.transfer.domain.model import L0_REQUIRED_FIELDS, TransferDetailLevel

pytestmark = [pytest.mark.transfer, pytest.mark.transfer_pkg]


def test_levels_by_receiving_layer() -> None:
    book = RuleBook()
    assert [(r.receiving_layer, r.level.value, r.max_words) for r in book.rules] == [
        (0, "executive", 400), (1, "managerial", 800), (2, "technical_summary", 1500),
        (3, "detailed_technical", 3000)]


def test_executive_rule_is_strategic_only() -> None:
    r = RuleBook().for_layer(0)
    assert r.aggregation is AggregationMode.BY_ISSUE
    assert (r.max_items, r.include_closed, r.show_people, r.show_documents) == (3, False, False, False)
    assert (r.show_gaps, r.show_capacity) == ("count", "none")
    assert r.required_fields == L0_REQUIRED_FIELDS
    assert r.ruleset().required_fields == L0_REQUIRED_FIELDS


def test_managerial_and_technical_rules() -> None:
    m = RuleBook().for_level("managerial")
    t = RuleBook().for_level(TransferDetailLevel.TECHNICAL_SUMMARY)
    assert (m.show_people, m.show_collaborators, m.show_gaps, m.show_capacity) == (True, False, "list", "counts")
    assert (t.aggregation, t.include_closed, t.show_collaborators) == (AggregationMode.ITEMS, True, True)
    assert (t.max_documents_per_item, t.show_gaps, t.show_capacity) == (3, "per_item", "per_person")


def test_ruleset_carries_layer_and_no_word_limit() -> None:
    rs = RuleBook().for_layer(2).ruleset()
    assert rs.layer.value == 2 and rs.detail_level is TransferDetailLevel.TECHNICAL_SUMMARY
    assert rs.max_words is None and rs.min_judge_score == 18


def test_unknown_layer_and_level() -> None:
    book = RuleBook(DEFAULT_RULES[:2])
    with pytest.raises(NotFoundError):
        book.for_layer(2)
    with pytest.raises(NotFoundError):
        book.for_level("technical_summary")


def test_rulebook_rejects_duplicates() -> None:
    with pytest.raises(InvariantError):
        RuleBook([DEFAULT_RULES[0], DEFAULT_RULES[0]])
    with pytest.raises(InvariantError):
        RuleBook([DEFAULT_RULES[1], replace(DEFAULT_RULES[1], receiving_layer=2)])


@pytest.mark.parametrize("changes", [
    {"max_items": 0}, {"max_words": 10}, {"show_gaps": "all"}, {"show_capacity": "hours"},
    {"show_people": False, "show_collaborators": True},
], ids=["items", "words", "gaps", "capacity", "collaborators"])
def test_invalid_rules(changes: dict) -> None:
    with pytest.raises(InvariantError):
        replace(DEFAULT_RULES[2], **changes)


def test_registry_comparison() -> None:
    book = RuleBook()
    good = {0: ("executive", 400), 1: ("managerial", 800), 2: ("technical_summary", 1500),
            3: ("detailed_technical", 3000), 4: ("peer", None)}
    assert book.registry_mismatches(good) == []
    bad = {**good, 1: ("executive", 900)}
    assert book.registry_mismatches(bad) == ["L1: registry level executive != rule managerial",
                                             "L1: registry max words 900 != rule 800"]
