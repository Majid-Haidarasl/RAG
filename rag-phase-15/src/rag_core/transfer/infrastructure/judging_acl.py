"""Anti-corruption layer: a drafted package → Phase 10 judge case and verdicts.

A package text is judged like a Phase 9 summary (output kind ``ike_summary``):
the FACTS block is the only source, the item ids must appear, a lead must sit
next to its own item, the knowledge gaps should be named. The rule judge works
offline; ``CombinedPackageJudge`` asks the rule judge and the LLM judge and
accepts only when both accept (the Phase 10 combined rule).
"""

from __future__ import annotations

from typing import Any

from rag_core.judging.application.services import judge_all
from rag_core.judging.domain.cases import Expectation, JudgeCase, SourceBlock
from rag_core.judging.domain.results import JudgeResult
from rag_core.judging.domain.rubric import OutputKind
from rag_core.transfer.domain.builder import PackageDraft
from rag_core.transfer.domain.review import JudgeVerdict

LANGUAGE_NAMES = {"fa": "Persian", "en": "English"}
AUDIENCE = {
    "executive": "the Board",
    "managerial": "the chief executive",
    "technical_summary": "the deputy",
    "detailed_technical": "the execution team",
}


def package_case(
    draft: PackageDraft,
    language: str,
    text: str | None = None,
    *,
    origin: str = "transfer-template",
    suffix: str = "",
) -> JudgeCase:
    level = draft.detail_level
    task = (
        f"Write the {LANGUAGE_NAMES.get(language, language)} {level} knowledge-transfer package of cycle "
        f"{draft.cycle_id} from {draft.source_node} to {AUDIENCE.get(level, draft.target_node)} "
        f"({draft.target_node}): the items with their status"
        + (" and lead executor" if draft.rule.show_people else "")
        + ", risks, decisions requested and knowledge gaps. Use only the facts."
    )
    case_id = f"P11-{draft.source_node}-{language}" + (f"-{suffix}" if suffix else "")
    return JudgeCase(
        case_id=case_id,
        kind=OutputKind.IKE_SUMMARY,
        language=language,
        task=task,
        output=draft.text(language) if text is None else text,
        sources=(SourceBlock("FACTS", "\n".join(draft.facts)),),
        expectation=Expectation(
            status="summary",
            items=draft.rendered.expected_items,
            item_leads=draft.rendered.expected_leads,
            gaps=draft.rendered.expected_gaps,
        ),
        status="summary",
        node=draft.source_node,
        origin=origin,
    )


def verdict_from(result: JudgeResult, language: str) -> JudgeVerdict:
    return JudgeVerdict(
        judge=result.judge,
        language=language,
        total=result.total,
        out_of=result.outcome.out_of,
        accepted=result.accepted,
        scores=dict(result.scores),
        reasons=tuple(result.outcome.reasons),
        notes=tuple(result.notes),
    )


class CaseJudgeAdapter:
    """Wraps one Phase 10 judge (rule or LLM) as a ``PackageJudgePort``."""

    def __init__(self, judge: Any, *, origin: str = "transfer-template") -> None:
        self.judge = judge
        self.name = str(getattr(judge, "name", "judge"))
        self.origin = origin
        self.results: list[JudgeResult] = []

    def judge_package(
        self, draft: PackageDraft, language: str, text: str | None = None
    ) -> list[JudgeVerdict]:
        origin = self.origin if text is None else "transfer-ai"
        result = judge_all(
            self.judge, [package_case(draft, language, text, origin=origin)]
        )[0]
        self.results.append(result)
        return [verdict_from(result, language)]


class CombinedPackageJudge:
    """Rule judge and LLM judge; accepted only when every judge accepts."""

    def __init__(self, *judges: Any) -> None:
        self.judges = judges
        self.name = "+".join(getattr(j, "name", "judge") for j in judges)

    def judge_package(
        self, draft: PackageDraft, language: str, text: str | None = None
    ) -> list[JudgeVerdict]:
        out: list[JudgeVerdict] = []
        for j in self.judges:
            out.extend(j.judge_package(draft, language, text))
        return out
