"""Anti-corruption layer: a key-issue brief -> Phase 10 judge case and verdicts.

A brief is judged like a Phase 9 summary (output kind ``ike_summary``): the
FACTS block is the only source, every key issue id must appear and the gap
subjects should be named. The rule judge works offline; with Ollama the LLM
judge is asked too and a brief is accepted only when every judge accepts.
"""

from __future__ import annotations

from typing import Any

from rag_core.judging.application.services import judge_all
from rag_core.judging.domain.cases import Expectation, JudgeCase, SourceBlock
from rag_core.judging.domain.results import JudgeResult
from rag_core.judging.domain.rubric import OutputKind
from rag_core.prioritization.domain.brief import KeyIssueBrief

LANGUAGE_NAMES = {"fa": "Persian", "en": "English"}


def brief_case(brief: KeyIssueBrief, text: str | None = None, *, origin: str = "priority-template",
               suffix: str = "") -> JudgeCase:
    task = (f"Write the {LANGUAGE_NAMES.get(brief.language, brief.language)} key-issue brief of cycle "
            f"{brief.cycle_id} for the chief executive: the key issues in priority order with their score and main "
            "factors, the open gaps on them, the next action and the open research gaps. Use only the facts.")
    case_id = f"P12-brief-{brief.language}" + (f"-{suffix}" if suffix else "")
    return JudgeCase(
        case_id=case_id,
        kind=OutputKind.IKE_SUMMARY,
        language=brief.language,
        task=task,
        output=brief.text if text is None else text,
        sources=(SourceBlock("FACTS", "\n".join(brief.facts)),),
        expectation=Expectation(status="summary", items=brief.items, gaps=brief.gaps),
        status="summary",
        node="N-CEO",
        origin=origin,
    )


def verdict_dict(result: JudgeResult) -> dict[str, Any]:
    return {"judge": result.judge, "total": result.total, "out_of": result.outcome.out_of,
            "accepted": result.accepted, "scores": dict(result.scores), "reasons": list(result.outcome.reasons),
            "notes": list(result.notes)}


class BriefJudge:
    """One Phase 10 judge (rule or LLM) for briefs; keeps every result."""

    def __init__(self, judge: Any) -> None:
        self.judge = judge
        self.name = str(getattr(judge, "name", "judge"))
        self.results: list[JudgeResult] = []

    def judge_brief(self, brief: KeyIssueBrief, text: str | None = None, *, origin: str = "priority-template",
                    suffix: str = "") -> JudgeResult:
        result = judge_all(self.judge, [brief_case(brief, text, origin=origin, suffix=suffix)])[0]
        self.results.append(result)
        return result


NEG_NUMBER = {"en": " Penalty 777 million toman.", "fa": " جریمهٔ ۷۷۷ میلیون تومان."}
NEG_ID = {"en": " See AR-ISS-099.", "fa": " به AR-ISS-099 نگاه کنید."}


def negative_brief_cases(brief: KeyIssueBrief) -> list[JudgeCase]:
    """Broken copies of the template: invented number, invented id, key issue lines removed."""
    base = brief_case(brief)
    lang = brief.language
    kept = [line for line in brief.text.splitlines() if not any(i in line for i in brief.items)]
    return [base.mutated("wrong_number", brief.text + NEG_NUMBER[lang]),
            base.mutated("fabricated_id", brief.text + NEG_ID[lang]),
            base.mutated("drop_items", "\n".join(kept))]
