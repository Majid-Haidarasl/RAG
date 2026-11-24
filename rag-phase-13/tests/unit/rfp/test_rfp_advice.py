"""Phase 13 advisory AI reply: JSON parsing and the grounding / invented-id check."""

import json

import pytest

from rag_core.qa.domain.fact_check import CitedFactValidator
from rag_core.rfp.domain.advice import (
    AiReply,
    ParsedReply,
    ReplyParseError,
    check_reply,
    ids_in,
    parse_reply,
)

pytestmark = [pytest.mark.rfp_gen]

FACTS = [
    "RFP AR-RFP-1403-07: Warehouse web reporting module. Owner N-SW; cycle 1403-Q2.",
    "Sub-issue AR-ISS-024/WEB (in_progress), owner N-SW-WEB.",
    "[REQ-EVALUATION] (mandatory) Weights are 60% technical and 40% financial.",
    "Feedback on proposal PRP-B: weighted score 75.2 of 100.",
]
ITEMS = ("AR-RFP-1403-07", "AR-ISS-024/WEB")


def reply(text: str, questions: object = None) -> str:
    data: dict = {"summary": text}
    if questions is not None:
        data["questions"] = questions
    return json.dumps(data, ensure_ascii=False)


def test_plain_json() -> None:
    p = parse_reply(
        reply("RFP AR-RFP-1403-07 buys a reporting module.", ["Who signs?"]), "summary"
    )
    assert (
        p.text.startswith("RFP AR-RFP-1403-07")
        and p.questions == ("Who signs?",)
        and p.mode == "json"
    )


def test_fenced_and_extracted_json() -> None:
    assert (
        parse_reply("```json\n" + reply("ok text") + "\n```", "summary").mode == "json"
    )
    p = parse_reply("Here it is: " + reply("ok text") + " thanks", "summary")
    assert p.mode == "json_extracted" and p.text == "ok text"


def test_questions_as_a_single_string() -> None:
    assert parse_reply(reply("t", "Is 60% fixed?"), "summary").questions == (
        "Is 60% fixed?",
    )


BAD = [
    ("", "empty"),
    ("no json here", "no JSON"),
    ("[1, 2]", "no JSON object|JSON object"),
    ('{"other": "x"}', "missing"),
    ('{"summary": "x", "questions": 3}', "list"),
    ('{"summary": "x" "questions"}', "invalid JSON|no JSON"),
]


def test_bad_replies() -> None:
    for raw, message in BAD:
        with pytest.raises(ReplyParseError, match=message):
            parse_reply(raw, "summary")


def test_the_key_depends_on_the_task() -> None:
    raw = json.dumps({"feedback": "PRP-B scored 75.2."})
    assert parse_reply(raw, "feedback").text == "PRP-B scored 75.2."
    with pytest.raises(ReplyParseError):
        parse_reply(raw, "summary")


def test_grounded_reply_names_the_items() -> None:
    p = ParsedReply(
        "RFP AR-RFP-1403-07 covers AR-ISS-024/WEB; weights 60% and 40%.", (), "json"
    )
    c = check_reply(p, FACTS, ITEMS, CitedFactValidator())
    assert (
        c.ok
        and c.grounded
        and c.invented_ids == ()
        and (c.mentioned, c.expected) == (2, 2)
    )
    assert c.to_dict()["ok"] is True


def test_invented_number_in_text_or_question() -> None:
    p = ParsedReply("RFP AR-RFP-1403-07 has weights 70% and 30%.", (), "json")
    c = check_reply(p, FACTS, ITEMS, CitedFactValidator())
    assert not c.ok and set(c.unsupported) == {"70", "30"}
    q = ParsedReply(
        "RFP AR-RFP-1403-07.", ("Is the budget 900 million toman?",), "json"
    )
    assert check_reply(q, FACTS, ITEMS, CitedFactValidator()).unsupported == ("900",)


def test_invented_record_ids_are_caught() -> None:
    p = ParsedReply(
        "PRP-C and REQ-BUDGET are part of AR-RFP-1403-07; see CRT-RISK.", (), "json"
    )
    c = check_reply(p, FACTS, ITEMS, CitedFactValidator())
    assert c.invented_ids == ("CRT-RISK", "PRP-C", "REQ-BUDGET") and not c.ok


def test_known_record_ids_and_sub_issues_pass() -> None:
    p = ParsedReply(
        "PRP-B was scored under REQ-EVALUATION for AR-RFP-1403-07 and AR-ISS-024/WEB.",
        (),
        "json",
    )
    assert check_reply(p, FACTS, ITEMS, CitedFactValidator()).invented_ids == ()


def test_ids_in_normalizes_persian_digits() -> None:
    assert ids_in(["شناسه AR-ISS-۰۲۴/WEB و PRP-A"]) == {"AR-ISS-024/WEB", "PRP-A"}


def test_ai_reply_to_dict() -> None:
    ai = AiReply("rfp_summary", "AR-RFP-1403-07", "fa", raw="x", error="empty reply")
    data = ai.to_dict()
    assert (
        data["status"] == "error"
        and data["text"] == ""
        and data["parse_mode"] == "error"
    )
    assert data["check"] is None and data["task"] == "rfp_summary"
