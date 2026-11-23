"""Proposal management use case: validate, ground, evaluate, give feedback, link knowledge.

``audit`` returns every problem at once (validator problems, evidence
failures and evaluation mismatches). Evaluation codes:
``published_mismatch`` (computed weighted score differs from the recorded
one), ``decision_mismatch`` (the recorded decision is not the top compliant
proposal) and ``no_winner``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from rag_core.projects.domain.evidence import DocumentTexts
from rag_core.projects.domain.validation import Problem
from rag_core.proposals.domain.evaluation import Evaluation, evaluate
from rag_core.proposals.domain.evidence import ProposalEvidence, ground_registry
from rag_core.proposals.domain.feedback import FeedbackDraft, build_feedback
from rag_core.proposals.domain.knowledge import KnowledgeBundle, link_knowledge
from rag_core.proposals.domain.model import ProposalRegistry
from rag_core.proposals.domain.validation import ProposalValidator
from rag_core.rfp.domain.blueprint import Blueprint
from rag_core.rfp.domain.evidence import NumberExtractor
from rag_core.shared_kernel.fact_ports import FactValidator


@dataclass
class ProposalAudit:
    problems: list[Problem] = field(default_factory=list)
    evidence: ProposalEvidence | None = None
    evaluation: Evaluation | None = None

    @property
    def ok(self) -> bool:
        return not self.problems

    @property
    def codes(self) -> list[str]:
        return list(dict.fromkeys(p.code for p in self.problems))

    def to_dict(self) -> dict[str, object]:
        return {"ok": self.ok, "problems": [p.__dict__ for p in self.problems],
                "evidence": self.evidence.to_dict() if self.evidence else None,
                "evaluation": self.evaluation.to_dict() if self.evaluation else None}


def evaluation_problems(ev: Evaluation) -> list[Problem]:
    out: list[Problem] = []
    for s in ev.scores:
        if s.published is not None and s.weighted is not None and not s.matches_published:
            out.append(Problem("published_mismatch", s.proposal_id,
                               f"computed {s.weighted}, recorded {s.published}"))
    w = ev.winner
    if w is None:
        out.append(Problem("no_winner", ev.rfp_id, "no compliant proposal with a full score"))
    elif ev.selected and w.proposal_id != ev.selected:
        out.append(Problem("decision_mismatch", ev.selected, f"top compliant proposal is {w.proposal_id}"))
    return out


class ProposalService:
    def __init__(self, blueprints: Iterable[Blueprint], documents: Iterable[str], texts: DocumentTexts,
                 fact_validator: FactValidator, numbers_in: NumberExtractor,
                 languages: Iterable[str] = ("fa", "en")) -> None:
        self.blueprints = {b.rfp_id: b for b in blueprints}
        self.validator = ProposalValidator(self.blueprints.values(), documents)
        self.texts = texts
        self.fact_validator = fact_validator
        self.numbers_in = numbers_in
        self.languages = tuple(languages)

    def blueprint(self, registry: ProposalRegistry) -> Blueprint | None:
        return self.blueprints.get(registry.rfp_id)

    def audit(self, registry: ProposalRegistry) -> ProposalAudit:
        out = ProposalAudit(self.validator.validate(registry))
        out.evidence = ground_registry(registry, self.texts, self.fact_validator, self.numbers_in, self.languages)
        for r in out.evidence.failures():
            code = "ungrounded_number" if ":" not in r.ref and "/" not in r.ref else "ungrounded_statement"
            out.problems.append(Problem(code, f"{r.ref}/{r.language}", "; ".join(r.missing)))
        bp = self.blueprint(registry)
        if bp is not None:
            out.evaluation = evaluate(bp, registry)
            out.problems.extend(evaluation_problems(out.evaluation))
        return out

    def feedback(self, registry: ProposalRegistry, evaluation: Evaluation) -> dict[str, dict[str, FeedbackDraft]]:
        bp = self.blueprint(registry)
        if bp is None:
            return {}
        return {p.proposal_id: {lang: build_feedback(bp, registry, evaluation, p.proposal_id, lang)
                                for lang in self.languages} for p in registry.proposals}

    def knowledge(self, registry: ProposalRegistry, evaluation: Evaluation, nodes: Iterable[str],
                  executors: Mapping[str, str]) -> KnowledgeBundle | None:
        bp = self.blueprint(registry)
        return None if bp is None else link_knowledge(bp, registry, evaluation, frozenset(nodes), executors)
