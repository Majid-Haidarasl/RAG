"""Phase 14 JSONL dataset adapter: round trip and rejected lines."""

import json
from pathlib import Path

import pytest

from rag_core.shared_kernel.errors import InvariantError
from rag_core.tuning.infrastructure.gold_jsonl import dump_gold, item_from_dict, item_to_dict, load_gold, parse_gold
from tests.fixtures.tuning.samples import answered_item, refusal_item

pytestmark = [pytest.mark.tuning, pytest.mark.eval_gold]


def test_round_trip() -> None:
    items = [answered_item("fa"), answered_item("en"), refusal_item("en")]
    again = parse_gold(dump_gold(items))
    assert again == items


def test_dump_is_one_utf8_object_per_line() -> None:
    text = dump_gold([answered_item("fa")])
    assert text.endswith("\n") and text.count("\n") == 1 and "پاسخ" in text
    assert json.loads(text)["expected_facts"] == [["30", "۳۰"], ["4", "۴"]]


def test_blank_lines_are_ignored(tmp_path: Path) -> None:
    path = tmp_path / "gold.jsonl"
    path.write_text("\n" + dump_gold([answered_item("en")]) + "\n\n", encoding="utf-8")
    assert [i.id for i in load_gold(path)] == ["T-P01-en"]


def test_invalid_json_names_the_line() -> None:
    with pytest.raises(InvariantError, match="line 2: invalid JSON"):
        parse_gold(dump_gold([answered_item("en")]) + "{nope\n")


def test_unknown_key() -> None:
    data = {**item_to_dict(answered_item()), "score": 3}
    with pytest.raises(InvariantError, match="unknown keys score"):
        item_from_dict(data)


def test_missing_required_key() -> None:
    data = item_to_dict(answered_item())
    del data["question"]
    with pytest.raises(InvariantError, match="missing question"):
        item_from_dict(data)


def test_bad_fact_groups() -> None:
    data = item_to_dict(answered_item())
    with pytest.raises(InvariantError, match="group is empty"):
        item_from_dict({**data, "expected_facts": [["30"], []]})
    with pytest.raises(InvariantError, match="list of lists"):
        item_from_dict({**data, "expected_facts": "30"})
    with pytest.raises(InvariantError, match="list of strings"):
        item_from_dict({**data, "expected_facts": [[30]]})


def test_bad_evidence() -> None:
    data = item_to_dict(answered_item())
    with pytest.raises(InvariantError, match="evidence needs exactly"):
        item_from_dict({**data, "evidence": [{"document_id": "AR-SW-022", "quote": "x"}]})


def test_not_an_object() -> None:
    with pytest.raises(InvariantError, match="JSON object"):
        parse_gold("[1, 2]\n")
