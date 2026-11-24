"""IKE summaries: digest, facts, templates, LLM prompt and fact check."""

import pytest

from rag_core.ike.application.services import IkeService, IkeSummaryService
from rag_core.ike.domain.summary import (
    SYSTEM_EN,
    SYSTEM_FA,
    digest,
    facts_lines,
    summary_prompt,
)
from rag_core.qa.domain.fact_check import CitedFactValidator
from rag_core.shared_kernel.errors import InvariantError
from tests.fixtures.ike.samples import NAMES, sample_issue, sample_referrals
from tests.fixtures.rag.fakes import FakeChat

pytestmark = [pytest.mark.ike, pytest.mark.ike_model]


def _graph():  # noqa: ANN202
    return IkeService().build(sample_issue(), sample_referrals())


def test_digest_reads_the_graph_back() -> None:
    d = digest(sample_issue(), _graph())
    assert d.item_ids == ("AR-ISS-050/HW", "AR-ISS-050/WIN", "AR-ISS-050/WEB")
    hw, win, web = d.items
    assert hw.lead == "EX-SAEED-AKBARI" and hw.knowledge == ("AR-HW-012", "AR-HW-015")
    assert win.depends_on == ("AR-ISS-050/HW",)
    assert (
        web.lead is None
        and web.collaborators == ("EX-YASAMAN-KARAMI",)
        and web.acceptance == "board"
    )
    assert len(d.lacks) == 4


def test_facts_lines() -> None:
    facts = facts_lines(digest(sample_issue(), _graph()), NAMES)
    assert (
        facts[0]
        == "issue AR-ISS-050: Sample delivery delay | owner N-LIB | status in_progress | progress 40%"
    )
    assert facts[1] == "sub-issues: AR-ISS-050/HW, AR-ISS-050/WIN, AR-ISS-050/WEB"
    hw = next(f for f in facts if f.startswith("sub-issue AR-ISS-050/HW"))
    assert "lead Saeed Akbari" in hw and "acceptance team_owner:N-HW-REP" in hw
    assert any(f.startswith("knowledge lack AR-ISS-050/WEB: AR-RFP-025") for f in facts)


@pytest.mark.parametrize("language", ["fa", "en"])
def test_template_summaries_are_grounded_and_cover_every_subissue(
    language: str,
) -> None:
    summary = IkeSummaryService(CitedFactValidator()).template(
        sample_issue(), _graph(), NAMES, language
    )
    assert summary.source == "template" and summary.language == language
    assert summary.check.grounded, summary.check.unsupported
    assert summary.check.coverage == "3/3"
    assert summary.check.claims > 0


def test_persian_template_uses_persian_names_and_statuses() -> None:
    text = (
        IkeSummaryService(CitedFactValidator())
        .template(sample_issue(), _graph(), NAMES, "fa")
        .text
    )
    assert NAMES["EX-SAEED-AKBARI"][1] in text
    assert "مسدود" in text and "AR-ISS-050/WIN" in text and "40٪" in text


def test_prompt_carries_facts_and_language() -> None:
    facts = ["issue AR-ISS-050: x | owner N-LIB"]
    system, user = summary_prompt(facts, "fa")
    assert system == SYSTEM_FA and facts[0] in user
    system, user = summary_prompt(facts, "en")
    assert system == SYSTEM_EN and "Mention every sub-issue id" in user


def test_llm_summary_grounded() -> None:
    reply = (
        "AR-ISS-050 is in progress at 40%. AR-ISS-050/HW is led by Saeed Akbari at N-HW-REP; "
        "AR-ISS-050/WIN waits for AR-ISS-050/HW; AR-ISS-050/WEB has no lead and lacks AR-RFP-025."
    )
    chat = FakeChat(reply=reply)
    summary = IkeSummaryService(CitedFactValidator(), chat).generate(
        sample_issue(), _graph(), NAMES, "en"
    )
    assert (
        summary.source == "llm"
        and summary.check.grounded
        and summary.check.coverage == "3/3"
    )
    system, user = chat.calls[0]
    assert system == SYSTEM_EN and "sub-issue AR-ISS-050/HW" in user


def test_llm_summary_with_invented_facts_is_not_grounded() -> None:
    chat = FakeChat(reply="AR-ISS-050/HW needs 12 more days and AR-HW-099.")
    summary = IkeSummaryService(CitedFactValidator(), chat).generate(
        sample_issue(), _graph(), NAMES, "fa"
    )
    assert not summary.check.grounded
    assert (
        "12" in summary.check.unsupported and "AR-HW-099" in summary.check.unsupported
    )
    assert summary.check.coverage == "1/3"
    assert summary.to_dict()["check"]["grounded"] is False  # type: ignore[index]


def test_llm_summary_needs_a_chat_model_and_a_known_language() -> None:
    service = IkeSummaryService(CitedFactValidator())
    with pytest.raises(InvariantError, match="chat model"):
        service.generate(sample_issue(), _graph(), NAMES, "en")
    with pytest.raises(InvariantError, match="language"):
        service.template(sample_issue(), _graph(), NAMES, "de")
