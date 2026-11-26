"""ExecutorMatcher rules on small synthetic profiles (AR-EXE-023 referral policy)."""

import pytest

from rag_core.executors.domain.matching import (
    ExecutorMatcher,
    MatchBreakdown,
    NodeRole,
    ReferralRequest,
    ReferralRole,
)
from rag_core.shared_kernel.errors import InvariantError
from tests.fixtures.executors.registry import make_executor

pytestmark = [pytest.mark.executors, pytest.mark.matching]

REQUEST = ReferralRequest(
    item_id="AR-ISS-050/WEB",
    owner_node="N-SW-WEB",
    supporting_nodes=("N-SW-UX",),
    related_documents=("AR-SW-017", "AR-RFP-025"),
    text="Reporting API contract and dashboard tests",
)


def _role(executor) -> ReferralRole:
    return ExecutorMatcher().evaluate(executor, REQUEST).role


def test_owner_node_member_with_two_terms_is_lead_candidate() -> None:
    person = make_executor(domains=("reporting API",), docs=("AR-SW-017",))
    match = ExecutorMatcher().evaluate(person, REQUEST)
    assert (
        match.role is ReferralRole.LEAD_CANDIDATE and match.node_role is NodeRole.OWNER
    )
    assert match.matched_terms == ("api", "report") and match.shared_documents == (
        "AR-SW-017",
    )
    assert match.eligible


def test_single_matching_keyword_is_not_enough() -> None:
    person = make_executor(domains=("dashboards",), docs=("AR-SW-017",))
    match = ExecutorMatcher().evaluate(person, REQUEST)
    assert match.role is ReferralRole.EXCLUDED
    assert any("single matching term (dashboard)" in r for r in match.reasons)
    assert any("outside the allowed referral domain" in r for r in match.reasons)


def test_supporting_node_member_with_shared_knowledge_is_collaborator() -> None:
    person = make_executor(
        node="N-SW-UX", domains=("brand colours",), docs=("AR-RFP-025",)
    )
    assert _role(person) is ReferralRole.COLLABORATOR


def test_supporting_node_member_with_two_terms_is_collaborator() -> None:
    person = make_executor(node="N-SW-UX", domains=("dashboard tests",))
    assert _role(person) is ReferralRole.COLLABORATOR


def test_supporting_node_member_without_signal_is_excluded() -> None:
    person = make_executor(node="N-SW-UX", domains=("brand colours",))
    assert _role(person) is ReferralRole.EXCLUDED


def test_outside_node_with_terms_and_knowledge_is_only_a_cross_node_candidate() -> None:
    person = make_executor(
        node="N-SW-MOB", domains=("web API contract",), docs=("AR-SW-017",)
    )
    match = ExecutorMatcher().evaluate(person, REQUEST)
    assert match.role is ReferralRole.CROSS_NODE_CANDIDATE and not match.eligible
    plan = ExecutorMatcher().plan([person], REQUEST)
    assert plan.recommended == [] and [
        m.executor_id for m in plan.cross_node_candidates
    ] == ["EX-TEST-PERSON"]


def test_outside_node_with_terms_but_no_knowledge_is_excluded() -> None:
    person = make_executor(node="N-SW-MOB", domains=("web API contract",))
    match = ExecutorMatcher().evaluate(person, REQUEST)
    assert match.role is ReferralRole.EXCLUDED
    assert any("not in the item's nodes" in r for r in match.reasons)


def test_zero_published_capacity_excludes() -> None:
    person = make_executor(domains=("reporting API",), hours=0)
    match = ExecutorMatcher().evaluate(person, REQUEST)
    assert match.role is ReferralRole.EXCLUDED
    assert any("0 h/week" in r for r in match.reasons)


def test_unpublished_capacity_is_noted_not_excluded() -> None:
    person = make_executor(domains=("reporting API",), hours=None)
    match = ExecutorMatcher().evaluate(person, REQUEST)
    assert match.role is ReferralRole.LEAD_CANDIDATE
    assert any("unit planning" in r for r in match.reasons)


def test_score_formula() -> None:
    assert MatchBreakdown(1.0, 0.5, 1.0).score == pytest.approx(0.85)
    assert MatchBreakdown(0.6, 2 / 3, 1.0).score == pytest.approx(0.74)
    person = make_executor(domains=("reporting API",), docs=("AR-SW-017",))
    match = ExecutorMatcher().evaluate(person, REQUEST)
    # node 1.0, knowledge 1/2, domain 2/4
    assert match.score == pytest.approx(0.4 + 0.15 + 0.15)


def test_plan_orders_by_score_then_terms_then_id_and_picks_lead() -> None:
    a = make_executor(
        "EX-ALPHA-ONE", "Alpha One", domains=("reporting API",), docs=("AR-SW-017",)
    )
    b = make_executor(
        "EX-BETA-TWO",
        "Beta Two",
        domains=("reporting API dashboard",),
        docs=("AR-SW-017",),
    )
    c = make_executor(
        "EX-GAMMA-THREE", "Gamma Three", node="N-SW-UX", docs=("AR-RFP-025",)
    )
    plan = ExecutorMatcher().plan([a, c, b], REQUEST)
    assert [m.executor_id for m in plan.recommended] == [
        "EX-BETA-TWO",
        "EX-ALPHA-ONE",
        "EX-GAMMA-THREE",
    ]
    assert plan.lead is not None and plan.lead.executor_id == "EX-BETA-TWO"
    assert [m.executor_id for m in plan.collaborators] == [
        "EX-ALPHA-ONE",
        "EX-GAMMA-THREE",
    ]
    data = plan.to_dict()
    assert (
        data["lead"] == "EX-BETA-TWO"
        and data["acceptance_authority"] == "team_owner:N-SW-WEB"
    )


def test_plan_without_owner_match_has_no_lead() -> None:
    c = make_executor(
        "EX-GAMMA-THREE", "Gamma Three", node="N-SW-UX", docs=("AR-RFP-025",)
    )
    plan = ExecutorMatcher().plan([c], REQUEST)
    assert plan.lead is None and plan.recommended_ids() == ["EX-GAMMA-THREE"]


def test_reserved_decision_is_accepted_by_the_board() -> None:
    req = ReferralRequest("AR-ISS-050/LEG", "N-ADM-LEG", reserved_decision=True)
    assert req.acceptance_authority == "board"
    assert req.nodes == ("N-ADM-LEG",)


def test_request_needs_owner_node() -> None:
    with pytest.raises(InvariantError):
        ReferralRequest("AR-ISS-050/HW", "")


def test_matcher_refuses_single_keyword_configuration() -> None:
    with pytest.raises(InvariantError, match="single matching keyword"):
        ExecutorMatcher(min_terms=1)
    with pytest.raises(InvariantError):
        ExecutorMatcher(min_terms=3, full_terms=2)
