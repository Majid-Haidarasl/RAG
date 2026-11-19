"""Judge services: the LLM judge (via ``JudgeModelPort``) and batch runs.

``LlmJudge`` renders the prompt for the case kind, asks the model, parses
the reply with ``JudgeOutputParser`` and applies the ``AcceptancePolicy``.
If the reply cannot be read, or misses criteria, it asks again once with a
short reminder (``retry_note``). A reply that still cannot be read is an
``error`` result, never an acceptance.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
import time

from rag_core.judging.domain.cases import JudgeCase
from rag_core.judging.domain.model import JudgeParseError
from rag_core.judging.domain.parser import JudgeOutputParser, ParsedJudgement
from rag_core.judging.domain.ports import CaseJudge, JudgeModelPort
from rag_core.judging.domain.prompts import JudgePromptSet
from rag_core.judging.domain.results import JudgeResult
from rag_core.judging.domain.rubric import Rubric
from rag_core.judging.domain.threshold import AcceptancePolicy
from rag_core.shared_kernel.errors import InvariantError

RAW_LIMIT = 4000


class LlmJudge:
    def __init__(
        self,
        rubric: Rubric,
        prompts: Mapping[str, JudgePromptSet],
        model: JudgeModelPort,
        *,
        name: str = "llm",
        retries: int = 1,
        sources_char_budget: int = 6000,
    ) -> None:
        if retries < 0:
            raise InvariantError("retries must be >= 0")
        self.rubric = rubric
        self.prompts = dict(prompts)
        self.model = model
        self.name = name
        self.retries = retries
        self.sources_char_budget = sources_char_budget
        self.parser = JudgeOutputParser(rubric)
        self.policy = AcceptancePolicy(rubric)

    def prompt_for(self, case: JudgeCase) -> JudgePromptSet:
        prompt = self.prompts.get(case.kind.value)
        if prompt is None:
            raise InvariantError(f"no judge prompt for output kind {case.kind.value!r}")
        return prompt

    def render(self, case: JudgeCase) -> tuple[str, str]:
        return self.prompt_for(case).render(case, self.rubric, sources_char_budget=self.sources_char_budget)

    def judge(self, case: JudgeCase) -> JudgeResult:
        prompt = self.prompt_for(case)
        system, user = prompt.render(case, self.rubric, sources_char_budget=self.sources_char_budget)
        t0 = time.perf_counter()
        raw = ""
        error = ""
        last: ParsedJudgement | None = None
        prompt_tokens = completion_tokens = 0
        attempts = 0
        for attempt in range(1, self.retries + 2):
            attempts = attempt
            message = user if attempt == 1 else f"{user}\n\n{prompt.retry_note}"
            result = self.model.generate(system, message)
            raw = result.text or ""
            prompt_tokens += result.prompt_tokens
            completion_tokens += result.completion_tokens
            try:
                parsed = self.parser.parse(raw)
            except JudgeParseError as exc:
                error = str(exc)
                continue
            last = parsed
            if parsed.complete:
                break
        seconds = time.perf_counter() - t0
        extra = {"raw": raw[:RAW_LIMIT], "seconds": seconds, "attempts": attempts,
                 "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}
        if last is None:
            return JudgeResult.for_case(case, self.name, {}, self.policy.error(error or "unparseable"),
                                        parse_mode="error", **extra)
        outcome = self.policy.decide(last.scores)
        return JudgeResult.for_case(case, self.name, last.scores, outcome, notes=last.issues, parse_mode=last.mode,
                                    warnings=last.warnings, **extra)


def judge_all(
    judge: CaseJudge,
    cases: list[JudgeCase],
    *,
    progress: Callable[[int, int, JudgeResult], None] | None = None,
    max_consecutive_errors: int = 2,
) -> list[JudgeResult]:
    """Judge every case. A failing model call becomes an ``error`` result; after
    more than ``max_consecutive_errors`` failures in a row the run stops."""
    policy: AcceptancePolicy | None = getattr(judge, "policy", None)
    out: list[JudgeResult] = []
    consecutive = 0
    for i, case in enumerate(cases, 1):
        try:
            result = judge.judge(case)
            consecutive = 0
        except InvariantError:
            raise
        except Exception as exc:  # noqa: BLE001 - transport / model failures are reported per case
            consecutive += 1
            if policy is None or consecutive > max_consecutive_errors:
                raise
            reason = f"model:{type(exc).__name__}: {exc}"[:300]
            result = JudgeResult.for_case(case, judge.name, {}, policy.error(reason), parse_mode="error")
        out.append(result)
        if progress is not None:
            progress(i, len(cases), result)
    return out
