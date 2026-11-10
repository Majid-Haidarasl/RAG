import pytest

from rag_core.judging.domain.model import (
    JudgeEvaluation,
    JudgeParseError,
    JudgeRubric,
    JudgeScore,
    JudgeThreshold,
    Verdict,
    parse_judge_output,
)
from tests.fakes.models import FakeJudge

pytestmark = pytest.mark.judging


def test_score_17_of_20_fails_and_18_passes() -> None:
    threshold = JudgeThreshold(18, 20)
    assert threshold.verdict(JudgeScore(17)) is Verdict.FAIL
    assert threshold.verdict(JudgeScore(18)) is Verdict.PASS
    failed = JudgeEvaluation.from_raw('{"score": 17, "out_of": 20}')
    assert failed.verdict is Verdict.FAIL
    assert any(e.name == "JudgeScoreBelowThreshold" for e in failed.events)
    passed = JudgeEvaluation.from_raw('{"score": 18, "out_of": 20}')
    assert passed.verdict is Verdict.PASS


def test_malformed_json_raises_parse_error() -> None:
    with pytest.raises(JudgeParseError):
        parse_judge_output("not-json")
    with pytest.raises(JudgeParseError):
        parse_judge_output('{"verdict": "ok"}')


def test_fake_judge_port_returns_configured_score() -> None:
    raw = FakeJudge(20).evaluate("summary", "source", JudgeRubric("default"))
    assert parse_judge_output(raw) == JudgeScore(20, 20)
