"""PackageReviewer: fact check + rule judge decide accepted / rejected."""

import pytest

from rag_core.qa.domain.fact_check import CitedFactValidator
from rag_core.transfer.domain.review import (
    JudgeVerdict,
    PackageReviewer,
    content_hash,
    ground,
)
from tests.fixtures.transfer.samples import (
    built,
    ceo,
    deputy,
    draft_for,
    empty_team,
    rule_reviewer,
    team_hw,
    team_mob,
    team_win,
)

pytestmark = [pytest.mark.transfer, pytest.mark.transfer_pkg]


def test_template_package_is_grounded_and_accepted() -> None:
    reviewer, adapter = rule_reviewer()
    p = reviewer.review(draft_for(team_hw(), "N-HW", 2))
    assert p.review.grounding["fa"].grounded and p.review.grounding["en"].grounded
    assert p.accepted and p.status == "accepted"
    assert p.review.total("rule", "en") >= 18 and p.review.total("rule", "fa") >= 18
    assert len(adapter.results) == 2


def test_managerial_and_executive_templates_are_accepted() -> None:
    sw = built(
        deputy("N-SW", "Software deputy"),
        "N-CEO",
        1,
        [built(team_win(), "N-SW", 2), built(team_mob(), "N-SW", 2)],
    )
    assert sw.accepted, sw.review.reasons
    board = built(ceo(), "N-BRD", 0, [sw])
    assert board.accepted, board.review.reasons


def test_empty_team_package_is_accepted() -> None:
    p = built(empty_team(), "N-HW", 2)
    assert p.accepted, p.review.reasons


def test_ground_flags_invented_number_and_id() -> None:
    d = draft_for(team_hw(), "N-HW", 2)
    check = ground(
        d.text("en") + " Penalty 777 million toman. See AR-ISS-099.",
        d.facts,
        CitedFactValidator(),
    )
    assert not check.grounded
    assert "777" in check.unsupported and "AR-ISS-099" in check.unsupported


class RejectingJudge:
    def judge_package(self, draft, language, text=None):  # noqa: ANN001, ANN201
        return [JudgeVerdict("strict", language, 10, 20, False)]


def test_judge_rejection_rejects_the_package() -> None:
    p = PackageReviewer(CitedFactValidator(), RejectingJudge()).review(
        draft_for(team_hw(), "N-HW", 2)
    )
    assert not p.accepted and p.status == "rejected"
    assert p.review.reasons == ("strict_fa:10/20", "strict_en:10/20")


def test_without_judge_only_grounding_counts() -> None:
    p = PackageReviewer(CitedFactValidator()).review(draft_for(team_hw(), "N-HW", 2))
    assert p.accepted and p.review.verdicts == ()


def test_record_and_hash() -> None:
    p = built(team_hw(), "N-HW", 2)
    record = p.to_record()
    assert (record.cycle_id, record.source_node, record.target_layer, record.items) == (
        "1403-Q2",
        "N-HW-REP",
        2,
        2,
    )
    assert record.content_hash == content_hash(p.content())
    assert record.content_hash == built(team_hw(), "N-HW", 2).to_record().content_hash
    assert record.payload["status"] == "accepted"
