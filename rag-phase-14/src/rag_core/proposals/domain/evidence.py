"""Proposal grounding: registered numbers and statements must be in the evidence documents.

* price, duration, every criterion score and the published weighted score
  must occur in the text of the proposal's evidence documents (fa and en);
* recorded feedback, clarification requests and the decision reason are
  checked with the shared-kernel ``FactValidator`` like Phase 12 statements.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal

from rag_core.projects.domain.evidence import DocumentTexts, GroundingResult, texts_for
from rag_core.proposals.domain.model import ProposalRecord, ProposalRegistry
from rag_core.rfp.domain.evidence import NumberExtractor, ground_statement
from rag_core.shared_kernel.fact_ports import FactValidator

LANGUAGES = ("fa", "en")


def registered_numbers(p: ProposalRecord) -> list[tuple[str, Decimal]]:
    out = [("price", p.price_mtoman), ("duration", Decimal(p.duration_weeks))]
    out.extend((f"score:{cid}", v) for cid, v in p.scores.items())
    if p.published_weighted is not None:
        out.append(("published", p.published_weighted))
    return out


@dataclass
class ProposalEvidence:
    numbers: list[GroundingResult] = field(default_factory=list)
    statements: list[GroundingResult] = field(default_factory=list)

    def failures(self) -> list[GroundingResult]:
        return [r for r in [*self.numbers, *self.statements] if not r.grounded]

    @property
    def ok(self) -> bool:
        return bool(self.numbers) and not self.failures()

    def grounded(self, kind: str, language: str) -> int:
        rows = self.numbers if kind == "numbers" else self.statements
        return sum(1 for r in rows if r.language == language and r.grounded)

    def total(self, kind: str, language: str) -> int:
        rows = self.numbers if kind == "numbers" else self.statements
        return sum(1 for r in rows if r.language == language)

    def to_dict(self) -> dict[str, object]:
        return {
            "numbers": [r.to_dict() for r in self.numbers],
            "statements": [r.to_dict() for r in self.statements],
        }


def ground_registry(
    registry: ProposalRegistry,
    texts: DocumentTexts,
    validator: FactValidator,
    numbers_in: NumberExtractor,
    languages: Iterable[str] = LANGUAGES,
) -> ProposalEvidence:
    out = ProposalEvidence()
    for lang in languages:
        for p in registry.proposals:
            sources = texts_for(p.evidence, lang, texts)
            found = {d.normalize() for d in numbers_in(sources)} if sources else set()
            missing = tuple(
                f"{name}={value}"
                for name, value in registered_numbers(p)
                if value.normalize() not in found
            )
            if not sources:
                missing = ("no evidence text",)
            out.numbers.append(
                GroundingResult(p.proposal_id, lang, not missing, missing)
            )
            if p.feedback(lang):
                out.statements.append(
                    ground_statement(
                        f"{p.proposal_id}/feedback",
                        p.feedback(lang),
                        p.evidence,
                        lang,
                        texts,
                        validator,
                    )
                )
            if p.clarifications(lang):
                out.statements.append(
                    ground_statement(
                        f"{p.proposal_id}/clarifications",
                        "; ".join(p.clarifications(lang)),
                        p.evidence,
                        lang,
                        texts,
                        validator,
                    )
                )
        d = registry.decision
        if d is not None and d.reason(lang):
            out.statements.append(
                ground_statement(
                    f"decision/{d.selected}",
                    d.reason(lang),
                    d.evidence,
                    lang,
                    texts,
                    validator,
                )
            )
    return out
