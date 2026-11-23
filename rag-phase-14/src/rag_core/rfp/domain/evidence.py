"""Blueprint grounding: every statement must be supported by its evidence documents.

Requirement statements and link roles are checked in Persian and English
with the shared-kernel ``FactValidator`` (Phase 8 ``CitedFactValidator``)
against the active text of the cited documents; each criterion weight (as a
percentage) must occur in the text of the criterion's evidence. Uses the
Phase 12 ``GroundingResult`` and ``texts_for``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from decimal import Decimal

from rag_core.projects.domain.evidence import DocumentTexts, GroundingResult, texts_for
from rag_core.rfp.domain.blueprint import Blueprint
from rag_core.shared_kernel.fact_ports import FactValidator, FactVerdict

NumberExtractor = Callable[[list[str]], set[Decimal]]
LANGUAGES = ("fa", "en")
OK = {FactVerdict.CONFIRMED, FactVerdict.CORRECTED}


def ground_statement(ref: str, statement: str, documents: tuple[str, ...], language: str, texts: DocumentTexts,
                     validator: FactValidator) -> GroundingResult:
    if not statement.strip():
        return GroundingResult(ref, language, False, ("no statement",))
    sources = texts_for(documents, language, texts)
    if not sources:
        return GroundingResult(ref, language, False, ("no evidence text",))
    report = validator.validate(statement, sources)
    missing = tuple(r.claim.raw_text for r in report.results if r.verdict not in OK)
    return GroundingResult(ref, language, not missing, missing)


@dataclass
class BlueprintEvidence:
    statements: list[GroundingResult] = field(default_factory=list)
    weights: list[GroundingResult] = field(default_factory=list)

    def grounded(self, language: str) -> int:
        return sum(1 for r in self.statements if r.language == language and r.grounded)

    def total(self, language: str) -> int:
        return sum(1 for r in self.statements if r.language == language)

    def failures(self) -> list[GroundingResult]:
        return [r for r in [*self.statements, *self.weights] if not r.grounded]

    @property
    def ok(self) -> bool:
        return bool(self.statements) and not self.failures()

    def to_dict(self) -> dict[str, object]:
        return {"statements": [r.to_dict() for r in self.statements], "weights": [r.to_dict() for r in self.weights]}


def ground_blueprint(bp: Blueprint, texts: DocumentTexts, validator: FactValidator, numbers_in: NumberExtractor,
                     languages: Iterable[str] = LANGUAGES) -> BlueprintEvidence:
    out = BlueprintEvidence()
    for lang in languages:
        for r in bp.requirements:
            out.statements.append(ground_statement(f"{bp.blueprint_id}/{r.requirement_id}", r.statement(lang),
                                                   r.evidence, lang, texts, validator))
        for link in bp.links:
            out.statements.append(ground_statement(f"{bp.blueprint_id}/{link.link_id}", link.role(lang),
                                                   link.evidence, lang, texts, validator))
        for c in bp.criteria:
            ref = f"{bp.blueprint_id}/{c.criterion_id}"
            sources = texts_for(c.evidence, lang, texts)
            if not sources:
                out.weights.append(GroundingResult(ref, lang, False, ("no evidence text",)))
                continue
            found = numbers_in(sources)
            ok = Decimal(c.percent).normalize() in found
            out.weights.append(GroundingResult(ref, lang, ok, () if ok else (f"weight={c.percent}%",)))
    return out
