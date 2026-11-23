"""Anti-corruption layer: an RFP draft or a bidder feedback -> Phase 10 judge case.

Both are judged like a Phase 9 summary (output kind ``ike_summary``): the FACTS
block is the only source, the listed ids must appear (citation) and the
expected subjects should be named (completeness). An RFP is a document, so
the script judges it with a rule judge whose character limit is
``judging.max_rfp_chars``; everything else uses the Phase 10 settings.
"""

from __future__ import annotations

from collections.abc import Sequence

from rag_core.judging.domain.cases import Expectation, JudgeCase, SourceBlock
from rag_core.judging.domain.rubric import OutputKind

LANGUAGE_NAMES = {"fa": "Persian", "en": "English"}
NEG_NUMBER = {"en": " Penalty 777 million toman.", "fa": " جریمهٔ ۷۷۷ میلیون تومان."}
NEG_ID = {"en": " See AR-ISS-099.", "fa": " به AR-ISS-099 نگاه کنید."}


def summary_case(case_id: str, language: str, task: str, output: str, facts: Sequence[str],
                 items: Sequence[str], gaps: Sequence[str] = (), *, node: str = "N-SW",
                 origin: str = "rfp-template") -> JudgeCase:
    return JudgeCase(
        case_id=case_id,
        kind=OutputKind.IKE_SUMMARY,
        language=language,
        task=task,
        output=output,
        sources=(SourceBlock("FACTS", "\n".join(facts)),),
        expectation=Expectation(status="summary", items=tuple(items), gaps=tuple(gaps)),
        status="summary",
        node=node,
        origin=origin,
    )


def rfp_task(rfp_id: str, language: str) -> str:
    return (f"Write the {LANGUAGE_NAMES.get(language, language)} request for proposal {rfp_id}: identity, the key "
            "issues it serves, the knowledge gaps, every requirement by section, the weighted criteria and the "
            "knowledge links. Use only the facts.")


def feedback_task(proposal_id: str, language: str) -> str:
    return (f"Write the {LANGUAGE_NAMES.get(language, language)} evaluation feedback for proposal {proposal_id}: "
            "weighted score and its parts, rank, the selected proposal, price and duration differences, the "
            "recorded feedback, open clarifications and where the result is recorded. Use only the facts.")


def negative_cases(base: JudgeCase, items: Sequence[str]) -> list[JudgeCase]:
    """Broken copies: invented number, invented id, every line naming a listed id removed."""
    text = base.output
    lang = base.language
    kept = [line for line in text.splitlines() if not any(i in line for i in items)]
    return [base.mutated("wrong_number", text + NEG_NUMBER.get(lang, NEG_NUMBER["en"])),
            base.mutated("fabricated_id", text + NEG_ID.get(lang, NEG_ID["en"])),
            base.mutated("drop_items", "\n".join(kept))]
