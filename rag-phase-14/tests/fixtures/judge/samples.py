"""Phase 10 judge test helpers: small cases, JSON replies and a scripted judge model."""

from __future__ import annotations

from dataclasses import dataclass, field
import json

from rag_core.judging.domain.cases import Expectation, JudgeCase, SourceBlock
from rag_core.judging.domain.rubric import OutputKind
from rag_core.models.domain.ports import LlmResult

FULL = {"grounding": 5, "correctness": 5, "citation": 4, "completeness": 3, "clarity": 3}

SLA_FA = SourceBlock("AR-SW-022 §4", "اولویت ۱ قطع کامل سرویس است: پاسخ ۳۰ دقیقه و رفع موقت ۴ ساعت. "
                     "اولویت ۲ پاسخ ۲ ساعت و رفع ۱۶ ساعت کاری دارد.", "AR-SW-022", 4, "fa")
SLA_EN = SourceBlock("AR-SW-022 §4", "Priority 1 is complete service outage: response within 30 minutes and temporary "
                     "restoration within 4 hours. Priority 2 requires response within 2 hours and resolution within "
                     "16 business hours.", "AR-SW-022", 4, "en")
HR_FA = SourceBlock("AR-HR-005 §5", "مرخصی ساعتی تا ۴ ساعت در روز و سقف ۱۶ ساعت در ماه است.", "AR-HR-005", 5, "fa")

GOOD_FA = "برای حادثهٔ اولویت ۱ پاسخ باید ظرف ۳۰ دقیقه و رفع موقت ظرف ۴ ساعت انجام شود [AR-SW-022 §4]."
GOOD_EN = "A Priority 2 incident requires a response within 2 hours and resolution within 16 business hours [AR-SW-022 §4]."


def reply(scores: dict[str, object] | None = None, **extra: object) -> str:
    return json.dumps({"scores": dict(FULL if scores is None else scores), **extra}, ensure_ascii=False)


def qa_fa(output: str = GOOD_FA, **changes: object) -> JudgeCase:
    base: dict[str, object] = dict(
        case_id="T-FA", kind=OutputKind.QA_ANSWER, language="fa",
        task="زمان پاسخ و رفع موقت برای حادثهٔ اولویت ۱ چقدر است؟", output=output, sources=(SLA_FA,),
        expectation=Expectation(status="answered", facts=(("30", "سی"), ("4", "چهار"))), node="N-SW-SUP",
        origin="test",
    )
    base.update(changes)
    return JudgeCase(**base)  # type: ignore[arg-type]


def qa_en(output: str = GOOD_EN, **changes: object) -> JudgeCase:
    base: dict[str, object] = dict(
        case_id="T-EN", kind=OutputKind.QA_ANSWER, language="en",
        task="What are the response and resolution targets for a Priority 2 incident?", output=output,
        sources=(SLA_EN,), expectation=Expectation(status="answered", facts=(("2", "two"), ("16", "sixteen"))),
        node="N-SW-SUP", origin="test",
    )
    base.update(changes)
    return JudgeCase(**base)  # type: ignore[arg-type]


def refusal_case(output: str, status: str, *, expected: str = "out_of_scope", escalation: str = "",
                 expected_escalation: str = "N-CEO", language: str = "fa") -> JudgeCase:
    return JudgeCase(
        case_id=f"T-REF-{status}", kind=OutputKind.QA_REFUSAL, language=language,
        task="سقف مرخصی بدون حقوق با تأیید معاون چند روز است؟" if language == "fa" else "What is the pet policy?",
        output=output, status=status, escalation=escalation, node="N-SW-WEB", origin="test",
        expectation=Expectation(status=expected, escalation=expected_escalation if expected == "out_of_scope" else ""),
    )


OUT_OF_SCOPE_FA = ("پاسخ این پرسش در دامنهٔ دانش گره N-SW-WEB نیست. پیشنهاد: پرسش به N-CEO ارجاع شود "
                   "(evidence owned outside scope by N-ADM-HR).")


@dataclass
class ScriptedJudgeModel:
    """``JudgeModelPort`` returning the given replies in order (the last one repeats)."""

    replies: list[str]
    calls: list[tuple[str, str]] = field(default_factory=list)

    def generate(self, system: str, user: str) -> LlmResult:
        self.calls.append((system, user))
        text = self.replies[min(len(self.calls) - 1, len(self.replies) - 1)]
        return LlmResult(text=text, prompt_tokens=len(user) // 4, completion_tokens=len(text) // 4)


class FailingModel:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, system: str, user: str) -> LlmResult:
        self.calls += 1
        raise ConnectionError("model down")
