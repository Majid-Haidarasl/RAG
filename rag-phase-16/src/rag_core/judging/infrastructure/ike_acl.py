"""Anti-corruption layer: Phase 9 IKE summaries → judge cases.

Reads only the plain fact lines written by ``ike.domain.summary.facts_lines``
(``sub-issue <id>: … | lead <name> | collaborators …`` and
``knowledge lack <id>: <document> (…)``) plus the executor name table
(English → Persian), so the judging context does not import the IKE graph.
"""

from __future__ import annotations

import re

from rag_core.judging.domain.cases import Expectation, JudgeCase, SourceBlock
from rag_core.judging.domain.rubric import OutputKind

_SUB_RE = re.compile(r"^sub-issue (?P<id>\S+): .*?\| lead (?P<lead>.+?) \| collaborators ")
_LACK_RE = re.compile(r"^knowledge lack (?P<id>\S+): (?P<target>\S+) \(")
LANGUAGE_NAMES = {"fa": "Persian", "en": "English"}


def summary_expectation(facts: list[str], names: dict[str, tuple[str, str]]) -> Expectation:
    fa_by_en = {en: fa for en, fa in names.values() if en}
    items: list[str] = []
    leads: list[tuple[str, tuple[str, ...]]] = []
    gaps: list[str] = []
    for line in facts:
        m = _SUB_RE.match(line)
        if m:
            item = m.group("id")
            items.append(item)
            lead = m.group("lead").strip()
            if lead and lead != "none":
                leads.append((item, tuple(x for x in (lead, fa_by_en.get(lead, "")) if x)))
            continue
        m = _LACK_RE.match(line)
        if m:
            gaps.append(m.group("target"))
    return Expectation(status="summary", items=tuple(items), item_leads=tuple(leads), gaps=tuple(gaps))


def summary_case(case_id: str, language: str, text: str, facts: list[str], names: dict[str, tuple[str, str]], *,
                 issue_id: str, origin: str, gold: str = "") -> JudgeCase:
    task = (f"Write a short {LANGUAGE_NAMES.get(language, language)} management summary of issue {issue_id}: "
            "the issue and its status, each sub-issue with its owner node and lead executor, and the knowledge "
            "gaps. Use only the facts.")
    return JudgeCase(
        case_id=case_id,
        kind=OutputKind.IKE_SUMMARY,
        language=language,
        task=task,
        output=text,
        sources=(SourceBlock("FACTS", "\n".join(facts)),),
        expectation=summary_expectation(facts, names),
        status="summary",
        origin=origin,
        gold=gold,
    )
