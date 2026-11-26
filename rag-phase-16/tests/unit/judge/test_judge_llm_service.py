"""Phase 10 LLM judge: prompt, parse, policy, retry and batch runs with fake models."""

from pathlib import Path

import pytest

from rag_core.judging.application.services import LlmJudge, judge_all
from rag_core.judging.domain.rubric import default_rubric
from rag_core.judging.domain.threshold import Decision
from rag_core.judging.infrastructure.prompt_yaml import load_judge_prompts
from rag_core.rag.infrastructure.ollama import OllamaChatModel, OllamaClient
from rag_core.shared_kernel.errors import InvariantError
from tests.fixtures.judge.samples import (
    FULL,
    OUT_OF_SCOPE_FA,
    FailingModel,
    ScriptedJudgeModel,
    qa_en,
    qa_fa,
    refusal_case,
    reply,
)
from tests.fixtures.rag.fakes import FakeChat, FakeOllamaServer

pytestmark = [pytest.mark.judging, pytest.mark.judge]

ROOT = Path(__file__).resolve().parents[3]
PROMPTS = load_judge_prompts(ROOT / "config" / "prompts" / "judge")


def _judge(model, retries: int = 1) -> LlmJudge:
    return LlmJudge(default_rubric(), PROMPTS, model, retries=retries)


def test_full_marks_reply_is_accepted() -> None:
    chat = FakeChat(reply=reply())
    result = _judge(chat).judge(qa_fa())
    assert result.accepted and result.total == 20 and result.scores == FULL
    assert (
        result.parse_mode == "json" and result.attempts == 1 and result.judge == "llm"
    )
    system, user = chat.calls[0]
    assert (
        "AR-SW-022 §4" in user
        and qa_fa().output in user
        and "grounding" in system + user
    )


def test_low_scores_are_rejected_with_issues_as_notes() -> None:
    scores = dict(FULL, grounding=2)
    result = _judge(FakeChat(reply=reply(scores, issues=["invented penalty"]))).judge(
        qa_en()
    )
    assert (
        result.decision is Decision.REJECT and "grounding 2<4" in result.outcome.reasons
    )
    assert result.notes == ("invented penalty",)


def test_unreadable_reply_is_retried_with_a_reminder() -> None:
    model = ScriptedJudgeModel(["I think it is fine.", reply()])
    result = _judge(model).judge(qa_en())
    assert result.accepted and result.attempts == 2
    assert model.calls[1][1].startswith(model.calls[0][1]) and len(
        model.calls[1][1]
    ) > len(model.calls[0][1])


def test_incomplete_reply_is_retried_once_and_then_kept() -> None:
    partial = reply({k: v for k, v in FULL.items() if k != "clarity"})
    model = ScriptedJudgeModel([partial, partial])
    result = _judge(model).judge(qa_en())
    assert (
        result.attempts == 2
        and "missing:clarity" in result.outcome.reasons
        and not result.accepted
    )


def test_reply_that_stays_unreadable_is_an_error_not_a_zero() -> None:
    model = ScriptedJudgeModel(["no idea"])
    result = _judge(model, retries=1).judge(qa_en())
    assert result.decision is Decision.ERROR and not result.accepted
    assert result.parse_mode == "error" and result.scores == {} and result.attempts == 2
    assert result.outcome.reasons[0].startswith("error:")


def test_no_retry_when_retries_is_zero() -> None:
    model = ScriptedJudgeModel(["no idea", reply()])
    result = _judge(model, retries=0).judge(qa_en())
    assert result.decision is Decision.ERROR and len(model.calls) == 1
    with pytest.raises(InvariantError):
        _judge(model, retries=-1)


def test_missing_prompt_for_kind() -> None:
    judge = LlmJudge(
        default_rubric(), {"qa_answer": PROMPTS["qa_answer"]}, FakeChat(reply=reply())
    )
    with pytest.raises(InvariantError):
        judge.judge(refusal_case(OUT_OF_SCOPE_FA, "out_of_scope", escalation="N-CEO"))


def test_judge_all_turns_model_failures_into_errors_then_stops() -> None:
    model = FailingModel()
    cases = [qa_en(case_id=f"C{i}") for i in range(2)]
    results = judge_all(_judge(model), cases, max_consecutive_errors=2)
    assert [r.decision for r in results] == [Decision.ERROR, Decision.ERROR]
    assert results[0].outcome.reasons[0].startswith("error:model:ConnectionError")
    with pytest.raises(ConnectionError):
        judge_all(
            _judge(FailingModel()),
            [qa_en(case_id=f"D{i}") for i in range(3)],
            max_consecutive_errors=2,
        )


def test_judge_all_reports_progress() -> None:
    seen: list[tuple[int, int]] = []
    results = judge_all(
        _judge(FakeChat(reply=reply())),
        [qa_fa(), qa_en()],
        progress=lambda i, n, r: seen.append((i, n)),
    )
    assert seen == [(1, 2), (2, 2)] and all(r.accepted for r in results)


def test_ollama_chat_model_sends_json_format_only_when_asked() -> None:
    with FakeOllamaServer(chat_reply=lambda messages: reply()) as srv:
        client = OllamaClient(srv.url, retries=0)
        judge_model = OllamaChatModel(
            client, options={"temperature": 0.0}, response_format="json"
        )
        result = _judge(judge_model).judge(qa_en())
        assert (
            result.accepted
            and result.prompt_tokens == 120
            and result.completion_tokens == 30
        )
        OllamaChatModel(client).generate("s", "u")
    chats = [body for path, body in srv.requests if path == "/api/chat"]
    assert chats[0]["format"] == "json" and chats[0]["options"] == {"temperature": 0.0}
    assert chats[0]["think"] is False
    assert "format" not in chats[1]
