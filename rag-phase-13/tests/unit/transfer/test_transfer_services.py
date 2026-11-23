"""TransferService (node → reviewed package) and SuggestionService (scripted chat model)."""

import json

import pytest

from rag_core.qa.domain.fact_check import CitedFactValidator
from rag_core.shared_kernel.errors import InvariantError, NotFoundError
from rag_core.transfer.application.services import SuggestionService, TransferService
from rag_core.transfer.domain.builder import TransferPackageBuilder
from rag_core.transfer.domain.levels import RuleBook
from tests.fixtures.rag.fakes import FakeChat
from tests.fixtures.transfer.samples import (
    CYCLE,
    VERSIONS,
    deputy,
    draft_for,
    knowledge_map,
    rule_reviewer,
    step,
    team_hw,
)

pytestmark = [pytest.mark.transfer, pytest.mark.transfer_pkg]


def service() -> TransferService:
    reviewer, _ = rule_reviewer()
    return TransferService(knowledge_map(team_hw(), deputy()), RuleBook(), TransferPackageBuilder(VERSIONS), reviewer)


def test_transfer_builds_reviewed_package() -> None:
    p = service().transfer(CYCLE, step("N-HW-REP", "N-HW", 3, 2), [], 0)
    assert p.accepted and p.detail_level == "technical_summary"
    up = service().transfer(CYCLE, step("N-HW", "N-CEO", 2, 1, order=2), [p], 1)
    assert up.detail_level == "managerial" and [i.item_id for i in up.items] == ["AR-ISS-024/HW"]


def test_unknown_node_gets_empty_knowledge_or_fails() -> None:
    svc = service()
    k = svc.knowledge_of("N-HW-SAL", 3)
    assert k.items == () and k.layer == 3
    with pytest.raises(NotFoundError):
        svc.transfer(CYCLE, step("N-LIB", "N-L5", 5, 4), [], 0)


def test_suggestion_service_accepts_grounded_reply() -> None:
    reply = json.dumps({"summary": "AR-ISS-024/HW is in progress; progress is 62%.", "raise": ["AR-ISS-024/HW"],
                        "reason": "It blocks AR-ISS-024."})
    chat = FakeChat(reply=reply)
    s = SuggestionService(chat, CitedFactValidator()).suggest(draft_for(team_hw(), "N-HW", 2), "en")
    assert s.status == "accepted" and s.parsed is not None and s.parsed.raise_ids == ("AR-ISS-024/HW",)
    assert "Facts:" in chat.calls[0][1]
    assert s.content_dict()["summary"].startswith("AR-ISS-024/HW")


def test_suggestion_service_reports_errors() -> None:
    d = draft_for(team_hw(), "N-HW", 2)
    bad = SuggestionService(FakeChat(reply="not json"), CitedFactValidator()).suggest(d, "fa")
    assert bad.status == "error" and "JSON" in bad.error

    class Broken:
        def generate(self, system, user):  # noqa: ANN001, ANN201
            raise ConnectionError("down")

    down = SuggestionService(Broken(), CitedFactValidator()).suggest(d, "en")
    assert down.status == "error" and down.error == "ConnectionError: down"
    with pytest.raises(InvariantError):
        SuggestionService(FakeChat(), CitedFactValidator()).suggest(d, "de")
