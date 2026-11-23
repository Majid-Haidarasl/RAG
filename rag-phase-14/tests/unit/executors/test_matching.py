import pytest

from rag_core.executors.domain.model import (
    Executor,
    ExpertiseTag,
    ReferralCapacity,
    canonical_person_name,
    suggest_executors,
)
from rag_core.shared_kernel.identifiers import ExecutorId, NodeIdentifier

pytestmark = pytest.mark.executors


def _exec(ident: str, name: str, node: str, domains: tuple[str, ...]) -> Executor:
    return Executor(
        identifier=ExecutorId(ident),
        display_name=name,
        home_node=NodeIdentifier(node),
        expertise=(ExpertiseTag("windows"),),
        allowed_referral_domains=domains,
        capacity=ReferralCapacity(12),
    )


def test_candidate_outside_allowed_referral_domain_is_excluded() -> None:
    roozbeh = _exec(
        "EX-ROOZBEH-MOHSENI",
        "Roozbeh Mohseni",
        "N-SW-WIN",
        ("warehouse desktop client", "kiosks", "customer-network installation"),
    )
    saeed = _exec(
        "EX-SAEED-AKBARI",
        "Saeed Akbari",
        "N-HW-REP",
        ("hardware repair", "raid diagnosis"),
    )
    matches = suggest_executors([roozbeh, saeed], "warehouse desktop client")
    assert matches == [roozbeh]


def test_rouzbeh_alias_normalizes_to_registry_spelling() -> None:
    assert canonical_person_name("Rouzbeh  Mohseni") == "Roozbeh Mohseni"
    person = _exec("EX-ROOZBEH-MOHSENI", "Rouzbeh Mohseni", "N-SW-WIN", ("windows",))
    assert person.display_name == "Roozbeh Mohseni"
