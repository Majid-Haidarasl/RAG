"""Phase 10 score parser: JSON, JSON in prose, repaired JSON, key-value lines, errors."""

from pathlib import Path

import pytest

from rag_core.judging.domain.model import JudgeParseError
from rag_core.judging.domain.parser import JudgeOutputParser, json_objects, repair_json, round_half_up, strip_wrappers
from rag_core.judging.domain.rubric import default_rubric
from rag_core.judging.infrastructure.calibration_json import load_parser_cases

pytestmark = [pytest.mark.judging, pytest.mark.judge]

ROOT = Path(__file__).resolve().parents[3]
CASES = load_parser_cases(ROOT / "data" / "judge" / "parser-cases.json")


def _parser() -> JudgeOutputParser:
    return JudgeOutputParser(default_rubric())


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_parser_fixture(case: dict) -> None:
    expect = case["expect"]
    if expect.get("error"):
        with pytest.raises(JudgeParseError):
            _parser().parse(case["raw"])
        return
    parsed = _parser().parse(case["raw"])
    assert parsed.scores == expect["scores"]
    assert parsed.mode == expect["mode"]
    assert list(parsed.missing) == expect.get("missing", [])
    for fragment in expect.get("warnings_contain", []):
        assert any(fragment in w for w in parsed.warnings), (fragment, parsed.warnings)


def test_fixture_file_covers_every_mode() -> None:
    modes = {c["expect"].get("mode", "error") for c in CASES}
    assert modes == {"json", "json_extracted", "json_repaired", "key_value", "error"}
    assert len(CASES) >= 15


def test_scores_come_back_in_rubric_order_with_total() -> None:
    parsed = _parser().parse('{"clarity": 3, "grounding": 5, "citation": 4, "correctness": 5, "completeness": 3}')
    assert list(parsed.scores) == ["grounding", "correctness", "citation", "completeness", "clarity"]
    assert parsed.total == 20 and parsed.complete


def test_reported_total_is_ignored_and_mismatch_reported() -> None:
    parsed = _parser().parse('{"scores": {"grounding": 2, "correctness": 2, "citation": 2, "completeness": 2, '
                             '"clarity": 2}, "total_score": 19}')
    assert parsed.total == 10 and parsed.reported_total == 19
    assert "total_mismatch:reported=19,computed=10" in parsed.warnings


def test_issues_are_kept_short() -> None:
    parsed = _parser().parse('{"scores": {"grounding": 5}, "issues": ["' + "x" * 500 + '", "", "second"]}')
    assert len(parsed.issues) == 2 and len(parsed.issues[0]) == 200
    assert parsed.missing == ("correctness", "citation", "completeness", "clarity")


def test_nested_value_with_out_of_is_rescaled() -> None:
    parsed = _parser().parse('{"scores": {"citation": {"score": 8, "out_of": 10}}}')
    assert parsed.scores == {"citation": 3}  # 8/10 of 4 = 3.2 -> 3
    assert "rescaled:citation" in parsed.warnings


def test_duplicate_alias_is_reported_once() -> None:
    parsed = _parser().parse('{"grounding": 5, "groundedness": 2, "clarity": 3}')
    assert parsed.scores["grounding"] == 5 and "duplicate:grounding" in parsed.warnings


def test_key_value_with_persian_digits_and_markdown() -> None:
    parsed = _parser().parse("**Grounding**: ۴\n- correctness = 5\nCitation quality: none\nclarity: 2 out of 3")
    assert parsed.mode == "key_value"
    assert parsed.scores == {"grounding": 4, "correctness": 5, "clarity": 2}


def test_unclosed_think_block_is_dropped() -> None:
    raw = "<think>scores could be {grounding: 1}</think>\n{\"scores\": {\"grounding\": 5, \"correctness\": 5, " \
          "\"citation\": 4, \"completeness\": 3, \"clarity\": 3}}"
    assert _parser().parse(raw).total == 20


@pytest.mark.parametrize("raw", ["", "   ", "[1, 2, 3]", '{"verdict": "accept"}', "no scores here"])
def test_unreadable_replies_raise(raw: str) -> None:
    with pytest.raises(JudgeParseError):
        _parser().parse(raw)


def test_criteria_without_numbers_raise() -> None:
    with pytest.raises(JudgeParseError):
        _parser().parse('{"scores": {"grounding": "good", "clarity": null}}')


def test_helpers() -> None:
    assert strip_wrappers("```json\n{\"a\": ۵}\n```").strip() == '{"a": 5}'
    assert json_objects('x {"a": {"b": 1}} y {"c": 2}') == ['{"a": {"b": 1}}', '{"c": 2}']
    assert json_objects('{"a": [1, {"b": "c') == ['{"a": [1, {"b": "c"}]}']
    assert repair_json("{a: 1, 'b': True,}") == '{"a": 1, "b": true}'
    assert [round_half_up(x) for x in (2.5, 3.49, -0.5, 0.5)] == [3, 3, 0, 1]
