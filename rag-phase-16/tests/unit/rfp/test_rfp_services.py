"""Phase 13 RFP use case: key issues -> candidates -> one draft per blueprint and language."""

import pytest

from rag_core.rfp.application.services import RfpService
from tests.fixtures.rfp.samples import (
    CYCLE,
    TARGETS,
    gap_views,
    item_view,
    key_views,
    shipped_blueprint,
)

pytestmark = [pytest.mark.rfp_gen]


def service(**kw) -> RfpService:
    args = {"categories": ("procurement",), "targets": TARGETS, **kw}
    return RfpService([shipped_blueprint()], **args)  # type: ignore[arg-type]


def test_one_rfp_in_two_languages() -> None:
    run = service().run(
        key_views(), gap_views(), {"AR-ISS-024/WEB": item_view()}, CYCLE
    )
    assert len(run.candidates) == 3 and [c.issue_id for c in run.sourcing] == [
        "AR-ISS-024",
        "AR-ISS-035",
    ]
    assert run.rfp_ids == ["AR-RFP-1403-07"] and set(run.drafts["AR-RFP-1403-07"]) == {
        "fa",
        "en",
    }
    assert len(run.all_drafts()) == 2
    en = run.drafts["AR-RFP-1403-07"]["en"]
    assert any(f.startswith("Sub-issue AR-ISS-024/WEB") for f in en.facts)


def test_no_sourcing_issue_no_rfp() -> None:
    run = service(targets={}, categories=()).run(key_views(), gap_views(), {}, CYCLE)
    assert run.sourcing == [] and run.drafts == {}
    assert {c.reason for c in run.candidates} == {"not_sourcing"}


def test_languages_and_to_dict() -> None:
    run = service().run(key_views(), gap_views(), {}, CYCLE, languages=("en",))
    data = run.to_dict()
    assert set(data) == {"candidates", "rfps"} and set(
        data["rfps"]["AR-RFP-1403-07"]
    ) == {"en"}  # type: ignore[index]


def test_blueprint_lookup() -> None:
    s = service()
    assert (
        s.blueprint("BP-WEB-REPORTING") is not None and s.blueprint("BP-NONE") is None
    )
