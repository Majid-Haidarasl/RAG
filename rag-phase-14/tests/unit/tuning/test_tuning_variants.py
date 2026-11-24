"""Phase 14 variant choice: the pick rule and the documented selection."""

import pytest

from rag_core.shared_kernel.errors import InvariantError
from rag_core.tuning.domain.variants import (
    KINDS,
    Candidate,
    Selection,
    SelectionRule,
    pick,
    selection_problems,
)

pytestmark = [pytest.mark.tuning, pytest.mark.eval_metrics]

RULE = SelectionRule("facts", True, (("rule_accept", True), ("seconds", False)), 0.02)


def cands(*rows: tuple[str, dict]) -> list[Candidate]:
    return [Candidate(v, m) for v, m in rows]


def test_rule_invariants() -> None:
    with pytest.raises(InvariantError, match="primary"):
        SelectionRule(" ")
    with pytest.raises(InvariantError, match="min_gain"):
        SelectionRule("facts", min_gain=-0.1)


def test_clear_winner() -> None:
    p = pick(cands(("base", {"facts": 0.7}), ("new", {"facts": 0.9})), RULE, "base")
    assert (
        p.winner == "new"
        and p.order == ("new", "base")
        and p.measured
        and "0.9" in p.reason
    )


def test_small_gain_keeps_the_baseline() -> None:
    p = pick(cands(("base", {"facts": 0.80}), ("new", {"facts": 0.81})), RULE, "base")
    assert p.winner == "base" and "gain below" in p.reason


def test_baseline_best() -> None:
    p = pick(cands(("base", {"facts": 0.9}), ("new", {"facts": 0.5})), RULE, "base")
    assert p.winner == "base" and "best value" in p.reason


def test_tie_breakers() -> None:
    rule = SelectionRule("facts", True, (("rule_accept", True), ("seconds", False)))
    p = pick(
        cands(
            ("base", {"facts": 0.8, "rule_accept": 0.5, "seconds": 3}),
            ("a", {"facts": 0.8, "rule_accept": 0.7, "seconds": 9}),
            ("b", {"facts": 0.8, "rule_accept": 0.7, "seconds": 4}),
        ),
        rule,
        "base",
    )
    assert p.order == ("b", "a", "base") and p.winner == "b"


def test_lower_is_better() -> None:
    rule = SelectionRule("leniency", False, (), 0.05)
    p = pick(
        cands(("baseline", {"leniency": 0.4}), ("strict", {"leniency": 0.1})),
        rule,
        "baseline",
    )
    assert p.winner == "strict"
    p = pick(
        cands(("baseline", {"leniency": 0.12}), ("strict", {"leniency": 0.1})),
        rule,
        "baseline",
    )
    assert p.winner == "baseline"


def test_unmeasured_sorts_last_and_keeps_baseline() -> None:
    p = pick(cands(("base", {"facts": None}), ("new", {})), RULE, "base")
    assert p.winner == "base" and not p.measured
    p = pick(cands(("base", {}), ("new", {"facts": 0.5})), RULE, "base")
    assert p.order[0] == "new" and p.winner == "new"


def test_pick_errors() -> None:
    with pytest.raises(InvariantError, match="nothing"):
        pick([], RULE, "base")
    with pytest.raises(InvariantError, match="baseline"):
        pick(cands(("a", {"facts": 1})), RULE, "base")


def test_pick_to_dict() -> None:
    d = pick(cands(("base", {"facts": 0.5})), RULE, "base").to_dict()
    assert d["winner"] == "base" and d["order"] == ["base"] and d["measured"] is True


def full_selection(**changes: Selection) -> dict[str, Selection]:
    sel = {k: Selection(k, "v1", "a reason with more than five words") for k in KINDS}
    sel.update(changes)
    return sel


def test_selection_complete() -> None:
    assert selection_problems(full_selection(), {k: ("v1",) for k in KINDS}) == []


def test_selection_problems() -> None:
    sel = full_selection(
        qa_prompt=Selection("qa_prompt", "v9", "a reason with more than five words"),
        retrieval=Selection("retrieval", "v1", "too short"),
    )
    del sel["ai_ids"]
    sel["speed"] = Selection("speed", "x", "a reason with more than five words")
    problems = selection_problems(sel, {"qa_prompt": ("v1",), "retrieval": ("v1",)})
    assert set(problems) == {
        "missing:ai_ids",
        "unknown_variant:qa_prompt=v9",
        "missing_reason:retrieval",
        "unknown_kind:speed",
    }
