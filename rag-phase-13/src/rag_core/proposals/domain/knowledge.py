"""Link an RFP and its outcome back to node knowledge.

Each blueprint link names the node (and optionally the executor) that owns a
piece of the RFP's knowledge; the outcome row ties the decision to the
sub-issue and key issues so later phases can find who knows what.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from rag_core.proposals.domain.evaluation import Evaluation
from rag_core.proposals.domain.model import ProposalRegistry
from rag_core.rfp.domain.blueprint import Blueprint


@dataclass(frozen=True)
class LinkRow:
    link_id: str
    rfp_id: str
    node: str
    executor: str
    requirements: tuple[str, ...]
    evidence: tuple[str, ...]
    valid: bool
    problem: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"link": self.link_id, "rfp_id": self.rfp_id, "node": self.node, "executor": self.executor,
                "requirements": list(self.requirements), "evidence": list(self.evidence), "valid": self.valid,
                "problem": self.problem}


@dataclass(frozen=True)
class OutcomeRow:
    rfp_id: str
    item: str
    issues: tuple[str, ...]
    owner_node: str
    selected: str
    weighted: str
    evidence: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"rfp_id": self.rfp_id, "item": self.item, "issues": list(self.issues), "owner_node": self.owner_node,
                "selected": self.selected, "weighted": self.weighted, "evidence": list(self.evidence)}


@dataclass
class KnowledgeBundle:
    links: list[LinkRow] = field(default_factory=list)
    outcome: OutcomeRow | None = None

    @property
    def valid(self) -> int:
        return sum(1 for r in self.links if r.valid)

    @property
    def nodes(self) -> list[str]:
        return list(dict.fromkeys(r.node for r in self.links))

    @property
    def executors(self) -> list[str]:
        return list(dict.fromkeys(r.executor for r in self.links if r.executor))

    @property
    def ok(self) -> bool:
        return bool(self.links) and self.valid == len(self.links) and self.outcome is not None \
            and bool(self.outcome.item) and bool(self.outcome.selected)

    def to_dict(self) -> dict[str, Any]:
        return {"links": [r.to_dict() for r in self.links], "outcome": self.outcome.to_dict() if self.outcome else None,
                "valid": self.valid, "nodes": self.nodes, "executors": self.executors, "ok": self.ok}


def link_knowledge(bp: Blueprint, registry: ProposalRegistry, evaluation: Evaluation, nodes: set[str] | frozenset[str],
                   executors: Mapping[str, str]) -> KnowledgeBundle:
    out = KnowledgeBundle()
    req_ids = {r.requirement_id for r in bp.requirements}
    for link in bp.links:
        problem = ""
        if link.node not in nodes:
            problem = "unknown_node"
        elif link.executor and link.executor not in executors:
            problem = "unknown_executor"
        elif link.executor and executors[link.executor] != link.node:
            problem = "executor_node_mismatch"
        elif any(r not in req_ids for r in link.requirements):
            problem = "unknown_requirement"
        out.links.append(LinkRow(link.link_id, bp.rfp_id, link.node, link.executor, link.requirements,
                                 link.evidence, not problem, problem))
    w = evaluation.winner
    selected = registry.decision.selected if registry.decision else ""
    evidence = registry.decision.evidence if registry.decision else ()
    out.outcome = OutcomeRow(bp.rfp_id, bp.item, bp.issues, bp.owner_node, selected,
                             str(w.weighted) if w is not None and w.weighted is not None else "", tuple(evidence))
    return out
