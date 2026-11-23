import pytest
from decimal import Decimal

from rag_core.rfp.domain.model import (
    AR_RFP_025_NOVIN_SCORES,
    AR_RFP_025_SHAFAGH_SCORES,
    AR_RFP_025_WEIGHTS,
    CriterionWeight,
    Rfp,
    compute_weighted_score,
)
from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.identifiers import NodeIdentifier, RfpId
from rag_core.rfp.domain.model import Proposal

pytestmark = pytest.mark.rfp


def test_rfp_without_criteria_fails_validation() -> None:
    with pytest.raises(InvariantError, match="criteria"):
        Rfp(
            identifier=RfpId("AR-RFP-1403-07"),
            title="Reporting module",
            owning_node=NodeIdentifier("N-SW"),
            criteria=(),
        )


def test_sixty_forty_weights_reproduce_published_ar_rfp_025_scores() -> None:
    shafagh = compute_weighted_score(AR_RFP_025_SHAFAGH_SCORES, AR_RFP_025_WEIGHTS)
    novin = compute_weighted_score(AR_RFP_025_NOVIN_SCORES, AR_RFP_025_WEIGHTS)
    assert shafagh.value == Decimal("78.8")
    assert novin.value == Decimal("75.2")

    rfp = Rfp(
        identifier=RfpId("AR-RFP-1403-07"),
        title="Reporting module",
        owning_node=NodeIdentifier("N-SW"),
        criteria=AR_RFP_025_WEIGHTS,
    )
    rfp.add_proposal(Proposal("Dadeh Pardaz Shafagh", dict(AR_RFP_025_SHAFAGH_SCORES)))
    rfp.add_proposal(Proposal("Novin Gozaresh Pars", dict(AR_RFP_025_NOVIN_SCORES)))
    assert rfp.proposal("Dadeh Pardaz Shafagh").weighted.value == Decimal("78.8")
    assert rfp.proposal("Novin Gozaresh Pars").weighted.value == Decimal("75.2")
