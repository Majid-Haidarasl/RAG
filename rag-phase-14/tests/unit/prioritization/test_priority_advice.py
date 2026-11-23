"""Phase 12 AI brief: prompt, JSON parsing and the grounding check (advice only)."""

import pytest

from rag_core.prioritization.domain.advice import (
    SYSTEM_EN,
    SYSTEM_FA,
    AdviceParseError,
    AiBrief,
    ParsedAdvice,
    advice_prompt,
    check_advice,
    parse_advice,
)
from rag_core.prioritization.domain.brief import KeyIssueBrief
from rag_core.qa.domain.fact_check import CitedFactValidator

pytestmark = [pytest.mark.prioritization]

FACTS = ("Cycle 1403-Q2, reporting cutoff 1403-06-31.",
         "Key issue 1: AR-ISS-024 — Delay. Status in_progress. Score 80.75 of 100.",
         "Key issue 2: AR-ISS-031 — Schedule. Status triaged. Score 33.92 of 100.")


def brief(language: str = "en") -> KeyIssueBrief:
    return KeyIssueBrief("1403-Q2", "1403-06-31", language, FACTS, "template", ("AR-ISS-024", "AR-ISS-031"),
                         ("AR-ISS-024/WIN",), ("AR-ISS-024", "AR-ISS-031", "AR-ISS-035"))


def test_prompt_in_both_languages() -> None:
    system, user = advice_prompt(brief())
    assert system == SYSTEM_EN and FACTS[1] in user and "Key issues: AR-ISS-024, AR-ISS-031." in user
    system, user = advice_prompt(brief("fa"))
    assert system == SYSTEM_FA and "مسئله‌های کلیدی: AR-ISS-024, AR-ISS-031." in user and '"order"' in user


def test_parse_plain_json() -> None:
    p = parse_advice('{"brief": " Handle AR-ISS-024 first. ", "order": ["AR-ISS-024", "ar-iss-031"]}')
    assert p == ParsedAdvice("Handle AR-ISS-024 first.", ("AR-ISS-024", "AR-ISS-031"), "json")


def test_parse_fenced_and_extracted_json() -> None:
    assert parse_advice('```json\n{"brief": "x AR-ISS-024", "order": []}\n```').mode == "json"
    p = parse_advice('Here it is: {"brief": "ok", "order": "AR-ISS-۰۲۴ then AR-ISS-031"} done')
    assert p.mode == "json_extracted" and p.order == ("AR-ISS-024", "AR-ISS-031")


def test_order_is_deduplicated_and_optional() -> None:
    assert parse_advice('{"brief": "ok", "order": ["AR-ISS-024", "AR-ISS-024"]}').order == ("AR-ISS-024",)
    assert parse_advice('{"brief": "ok"}').order == ()


@pytest.mark.parametrize("raw", ["", "no json here", "{broken", '["a"]', '{"order": []}', '{"brief": "  "}',
                                 '{"brief": "ok", "order": 5}'])
def test_bad_replies_raise(raw: str) -> None:
    with pytest.raises(AdviceParseError):
        parse_advice(raw)


def test_grounded_advice_is_ok() -> None:
    p = ParsedAdvice("Handle AR-ISS-024 first (score 80.75 of 100), then AR-ISS-031.", ("AR-ISS-024", "AR-ISS-031"),
                     "json")
    check = check_advice(p, brief(), CitedFactValidator())
    assert check.ok and check.same_top and check.mentioned == 2 and check.invented_ids == ()
    assert check.to_dict()["ok"] is True


def test_invented_number_and_id_are_caught() -> None:
    p = ParsedAdvice("Pay 555 million toman on AR-ISS-099.", ("AR-ISS-031", "AR-ISS-099"), "json")
    check = check_advice(p, brief(), CitedFactValidator())
    assert not check.ok and not check.grounded and any("555" in u for u in check.unsupported)
    assert check.invented_ids == ("AR-ISS-099",) and not check.same_top and check.mentioned == 0


def test_ranked_but_not_key_issue_is_not_invented() -> None:
    p = ParsedAdvice("AR-ISS-024 comes first.", ("AR-ISS-024", "AR-ISS-035"), "json")
    assert check_advice(p, brief(), CitedFactValidator()).invented_ids == ()


def test_ai_brief_to_dict() -> None:
    assert AiBrief("en", "error", error="timeout").to_dict()["parse_mode"] == "error"
    p = ParsedAdvice("ok", ("AR-ISS-024",), "json")
    data = AiBrief("fa", "accepted", raw="{}", parsed=p, seconds=1.23456).to_dict()
    assert data["order"] == ["AR-ISS-024"] and data["seconds"] == 1.235 and data["check"] is None
