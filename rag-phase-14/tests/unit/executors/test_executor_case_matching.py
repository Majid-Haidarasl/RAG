"""AR-ISS-024 (Azarpakhsh): matcher output vs the executors named in the issue registry."""

import pytest

from rag_core.executors.application.services import ExecutorMatchingService, role_counts
from rag_core.executors.domain.matching import ReferralRole
from rag_core.executors.infrastructure.issues_acl import referral_requests
from rag_core.executors.infrastructure.memory import InMemoryExecutorRepository
from tests.fixtures.executors.registry import shipped_executors
from tests.fixtures.issues.seed import azarpakhsh, seed_issues

pytestmark = [pytest.mark.executors, pytest.mark.matching]

EXPECTED = {
    "AR-ISS-024/HW": ("EX-SAEED-AKBARI", {"EX-SAEED-AKBARI", "EX-FARZANEH-JAVADI", "EX-EHSAN-DAVARI"}),
    "AR-ISS-024/WIN": ("EX-ROOZBEH-MOHSENI", {"EX-ROOZBEH-MOHSENI"}),
    "AR-ISS-024/WEB": ("EX-NAZANIN-FARAHANI", {"EX-NAZANIN-FARAHANI", "EX-HANIEH-SAADATI", "EX-YASAMAN-KARAMI"}),
    "AR-ISS-024/LEG": ("EX-MAHSA-JALALI", {"EX-MAHSA-JALALI", "EX-REZA-ABBASI"}),
}


def _service() -> ExecutorMatchingService:
    return ExecutorMatchingService(InMemoryExecutorRepository(shipped_executors()))


def _plans():  # noqa: ANN202
    return {p.request.item_id: p for p in _service().plans(referral_requests(azarpakhsh()))}


def test_one_request_per_subissue_in_position_order() -> None:
    requests = referral_requests(azarpakhsh())
    assert [r.item_id for r in requests] == list(EXPECTED)
    hw = requests[0]
    assert hw.owner_node == "N-HW-REP" and hw.supporting_nodes == ("N-HW-ADV", "N-HW-ASM")
    assert "RAID controller" in hw.text and hw.named_executors == ("Saeed Akbari", "Farzaneh Javadi", "Ehsan Davari")


@pytest.mark.parametrize("item", list(EXPECTED))
def test_recommended_executors_match_the_registry(item: str) -> None:
    lead, team = EXPECTED[item]
    plan = _plans()[item]
    assert set(plan.recommended_ids()) == team
    assert plan.lead is not None and plan.lead.executor_id == lead


def test_seed_comparison_resolves_rouzbeh_alias_and_agrees() -> None:
    svc = _service()
    seeds = [svc.compare_with_seed(p) for p in svc.plans(referral_requests(azarpakhsh()))]
    assert all(s.agrees for s in seeds), [s.to_dict() for s in seeds]
    win = next(s for s in seeds if s.item_id == "AR-ISS-024/WIN")
    assert win.named == ("Rouzbeh Mohseni",) and win.resolved == ("EX-ROOZBEH-MOHSENI",)


def test_web_team_member_with_one_matching_term_is_excluded() -> None:
    kian = _plans()["AR-ISS-024/WEB"].match_for("EX-KIAN-RAZAVI")
    assert kian.role is ReferralRole.EXCLUDED
    assert kian.matched_terms == ("web",)
    assert any("single matching term" in r for r in kian.reasons)


@pytest.mark.parametrize(
    ("item", "executor_id"),
    [("AR-ISS-024/WEB", "EX-AMIN-TOURANI"), ("AR-ISS-024/HW", "EX-ROOZBEH-MOHSENI"),
     ("AR-ISS-024/HW", "EX-KAMRAN-NIKPOUR"), ("AR-ISS-024/WIN", "EX-FARZANEH-JAVADI")],
)
def test_policy_exclusions(item: str, executor_id: str) -> None:
    assert _plans()[item].match_for(executor_id).role is ReferralRole.EXCLUDED


def test_supporting_finance_member_joins_the_contract_subissue() -> None:
    reza = _plans()["AR-ISS-024/LEG"].match_for("EX-REZA-ABBASI")
    assert reza.role is ReferralRole.COLLABORATOR
    assert reza.shared_documents == ("AR-FIN-010",) and reza.matched_terms == ()


def test_reserved_contract_decision_goes_to_the_board() -> None:
    plans = _plans()
    assert plans["AR-ISS-024/LEG"].request.acceptance_authority == "board"
    assert plans["AR-ISS-024/HW"].request.acceptance_authority == "team_owner:N-HW-REP"


def test_executor_load_counts_lead_and_collaborator_referrals() -> None:
    svc = _service()
    plans = svc.plans(referral_requests(azarpakhsh()))
    load = {row.executor_id: row for row in svc.load(plans)}
    assert load["EX-SAEED-AKBARI"].lead == ["AR-ISS-024/HW"]
    assert load["EX-HANIEH-SAADATI"].collaborator == ["AR-ISS-024/WEB"]
    assert load["EX-KIAN-RAZAVI"].referrals == 0
    assert sum(1 for row in load.values() if row.referrals) == 9
    counts = role_counts(plans)
    assert counts["lead_candidate"] == 5  # Hanieh is a second lead candidate on WEB
    assert counts["lead_candidate"] + counts["collaborator"] == 9
    assert sum(counts.values()) == 4 * 15


def test_flat_issues_become_one_request_each() -> None:
    flat = [i for i in seed_issues() if not i.subissues]
    assert flat
    for issue in flat:
        requests = referral_requests(issue)
        assert len(requests) == 1 and requests[0].item_id == str(issue.identifier)
        assert str(issue.identifier) not in requests[0].related_documents
