"""Registry validation against the RFP blueprint. Never raises; returns ``Problem`` values.

Codes: ``unknown_rfp``, ``duplicate_id``, ``unknown_criterion``, ``missing_score``,
``score_range``, ``unknown_section``, ``missing_section``, ``unknown_document``,
``missing_evidence``, ``decision_missing``, ``decision_unknown``.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from decimal import Decimal

from rag_core.projects.domain.validation import Problem
from rag_core.proposals.domain.model import ProposalRegistry
from rag_core.rfp.domain.blueprint import Blueprint

SCORE_MIN = Decimal("0")
SCORE_MAX = Decimal("100")


class ProposalValidator:
    def __init__(
        self, blueprints: Iterable[Blueprint], documents: Iterable[str]
    ) -> None:
        self.by_rfp = {b.rfp_id: b for b in blueprints}
        self.documents = set(documents)

    def _docs(self, ref: str, docs: tuple[str, ...]) -> list[Problem]:
        if not docs:
            return [Problem("missing_evidence", ref, "no evidence document")]
        return [
            Problem("unknown_document", ref, f"{d} is not in the corpus")
            for d in docs
            if d not in self.documents
        ]

    def validate(self, registry: ProposalRegistry) -> list[Problem]:
        out: list[Problem] = []
        bp = self.by_rfp.get(registry.rfp_id)
        if bp is None:
            out.append(
                Problem("unknown_rfp", registry.rfp_id, "no blueprint with this RFP id")
            )
        for pid, n in Counter(registry.ids).items():
            if n > 1:
                out.append(Problem("duplicate_id", pid, f"registered {n} times"))
        criteria = {c.criterion_id for c in bp.criteria} if bp else set()
        sections = set(bp.response_sections) if bp else set()
        for p in registry.proposals:
            ref = p.proposal_id
            if bp is not None:
                for cid in sorted(set(p.scores) - criteria):
                    out.append(
                        Problem(
                            "unknown_criterion",
                            f"{ref}/{cid}",
                            "criterion is not in the RFP",
                        )
                    )
                for cid in sorted(criteria - set(p.scores)):
                    out.append(
                        Problem(
                            "missing_score",
                            f"{ref}/{cid}",
                            "no score for this criterion",
                        )
                    )
                for s in sorted(set(p.sections) - sections):
                    out.append(
                        Problem(
                            "unknown_section",
                            f"{ref}/{s}",
                            "section is not asked for in the RFP",
                        )
                    )
                for s in bp.response_sections:
                    if s not in p.sections:
                        out.append(
                            Problem(
                                "missing_section",
                                f"{ref}/{s}",
                                "required response section is missing",
                            )
                        )
            for cid, score in p.scores.items():
                if not SCORE_MIN <= score <= SCORE_MAX:
                    out.append(
                        Problem(
                            "score_range", f"{ref}/{cid}", f"{score} is outside 0..100"
                        )
                    )
            out.extend(self._docs(ref, p.evidence))
        d = registry.decision
        if d is None:
            out.append(
                Problem("decision_missing", registry.rfp_id, "no recorded decision")
            )
        else:
            if registry.get(d.selected) is None:
                out.append(
                    Problem(
                        "decision_unknown",
                        d.selected,
                        "selected proposal is not registered",
                    )
                )
            out.extend(self._docs(f"decision/{d.selected}", d.evidence))
        return out
