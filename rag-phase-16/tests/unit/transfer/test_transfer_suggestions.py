"""AI transfer suggestions: prompt, JSON parsing and the fact check (no model is called)."""

import json

import pytest

from rag_core.qa.domain.fact_check import CitedFactValidator
from rag_core.transfer.domain.suggestions import (
    SuggestionParseError,
    candidate_ids,
    check_suggestion,
    parse_suggestion,
    suggestion_prompt,
)
from tests.fixtures.transfer.samples import (
    built,
    ceo,
    deputy,
    draft_for,
    team_hw,
    team_mob,
    team_win,
)

pytestmark = [pytest.mark.transfer, pytest.mark.transfer_pkg]


def board_draft():
    extra = [team_win(), team_mob()]
    sw = built(
        deputy("N-SW", "Software deputy"),
        "N-CEO",
        1,
        [built(n, "N-SW", 2) for n in extra],
    )
    d = draft_for(ceo(), "N-BRD", 0, [sw])
    d.omitted = ("AR-ISS-035",)
    return d


def test_prompt_contains_facts_ids_and_audience() -> None:
    d = draft_for(team_hw(), "N-HW", 2)
    system, user = suggestion_prompt(d, "en")
    assert "Use only the facts" in system
    assert d.facts[0] in user
    assert "Selectable ids: AR-ISS-024/HW, AR-ISS-034." in user
    assert "the deputy" in user and "at most 8 sentences" in user


def test_persian_prompt() -> None:
    system, user = suggestion_prompt(board_draft(), "fa")
    assert "فقط از واقعیت‌های داده‌شده استفاده کن" in system
    assert "هیئت‌مدیره" in user and "حداکثر 4 جمله" in user


def test_candidates_include_omitted_items() -> None:
    assert candidate_ids(board_draft()) == (
        "AR-ISS-024/WIN",
        "AR-ISS-031",
        "AR-ISS-035",
    )


def test_parse_plain_and_fenced_json() -> None:
    raw = json.dumps(
        {
            "summary": "AR-ISS-024/WIN is blocked.",
            "raise": ["ar-iss-024/win"],
            "reason": "Blocked.",
        }
    )
    p = parse_suggestion(raw)
    assert (p.summary, p.raise_ids, p.reason, p.mode) == (
        "AR-ISS-024/WIN is blocked.",
        ("AR-ISS-024/WIN",),
        "Blocked.",
        "json",
    )
    fenced = parse_suggestion("```json\n" + raw + "\n```")
    assert fenced.mode == "json"
    extracted = parse_suggestion("Here you go: " + raw + " thanks")
    assert extracted.mode == "json_extracted"


def test_parse_persian_digits_and_string_raise() -> None:
    p = parse_suggestion(
        json.dumps(
            {"summary": "خلاصه", "raise": "AR-ISS-۰۳۱ و AR-ISS-024/WIN"},
            ensure_ascii=False,
        )
    )
    assert p.raise_ids == ("AR-ISS-031", "AR-ISS-024/WIN")
    assert p.reason == ""


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "no json here",
        "[1, 2]",
        '{"summary": ""}',
        '{"summary": "x", "raise": 5}',
        '{"summary": "x", "raise": [1, }',
    ],
    ids=["empty", "no_json", "list", "empty_summary", "bad_raise", "broken"],
)
def test_parse_errors(raw: str) -> None:
    with pytest.raises(SuggestionParseError):
        parse_suggestion(raw)


def test_check_accepts_grounded_suggestion_with_addition() -> None:
    d = board_draft()
    p = parse_suggestion(
        json.dumps(
            {
                "summary": "AR-ISS-024/WIN is blocked; the decision amount is 850 million toman.",
                "raise": ["AR-ISS-024/WIN", "AR-ISS-035"],
                "reason": "It blocks delivery.",
            }
        )
    )
    check = check_suggestion(p, d, CitedFactValidator())
    assert check.ok
    assert check.additions == ("AR-ISS-035",)
    assert check.known_raise == ("AR-ISS-024/WIN", "AR-ISS-035")


def test_check_rejects_invented_ids_and_numbers() -> None:
    d = board_draft()
    p = parse_suggestion(
        json.dumps(
            {
                "summary": "Pay 999 million toman for AR-ISS-077.",
                "raise": ["AR-ISS-077"],
            }
        )
    )
    check = check_suggestion(p, d, CitedFactValidator())
    assert not check.ok
    assert check.invented_ids == ("AR-ISS-077",)
    assert not check.grounding.grounded
