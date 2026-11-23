"""Executor matching for one work item (an issue or a sub-issue).

AR-EXE-023 rules applied here:

* a profile is a competence and authority boundary, not an automatic
  assignment: the team owner decomposes first, then checks the permitted
  domain and capacity;
* reputation or a single matching skill keyword is insufficient: at least
  ``min_terms`` (2) distinct profile terms must occur in the item text;
* anyone outside the allowed referral domain is excluded (policy item 11).

Three explainable signals per executor:

``node``       home node is the item's owner node (1.0), a supporting node (0.6) or not involved (0.0);
``knowledge``  share of the item's related documents the executor holds as authoritative knowledge;
``domain``     distinct profile terms found in the item text, capped at ``full_terms`` (4).

``score = 0.4·node + 0.3·knowledge + 0.3·domain``.

Roles:

* ``lead_candidate``: member of the owner node with a domain match;
* ``collaborator``: member of a supporting node with a domain match or a
  shared knowledge document (the team owner already listed the node);
* ``cross_node_candidate``: not in the item's nodes but domain match and
  shared knowledge; reported for the team owner, never recommended;
* ``excluded``: everything else, with the reason.

The plan's lead is the best lead candidate; the other recommended
executors are collaborators. Ties break on more matched terms, then id.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from rag_core.executors.domain.expertise import ExpertiseProfile, terms
from rag_core.executors.domain.model import Executor
from rag_core.shared_kernel.errors import InvariantError

W_NODE = 0.4
W_KNOWLEDGE = 0.3
W_DOMAIN = 0.3
SUPPORTING_NODE_WEIGHT = 0.6
MIN_TERMS = 2
FULL_TERMS = 4


class NodeRole(StrEnum):
    OWNER = "owner"
    SUPPORTING = "supporting"
    NONE = "none"


class ReferralRole(StrEnum):
    LEAD_CANDIDATE = "lead_candidate"
    COLLABORATOR = "collaborator"
    CROSS_NODE_CANDIDATE = "cross_node_candidate"
    EXCLUDED = "excluded"


@dataclass(frozen=True)
class ReferralRequest:
    """What the executors context needs to know about a work item (via the issues ACL)."""

    item_id: str
    owner_node: str
    supporting_nodes: tuple[str, ...] = ()
    related_documents: tuple[str, ...] = ()
    text: str = ""
    reserved_decision: bool = False
    named_executors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.item_id.strip() or not self.owner_node.strip():
            raise InvariantError("a referral request needs an item id and an owner node")

    @property
    def nodes(self) -> tuple[str, ...]:
        return (self.owner_node, *(n for n in self.supporting_nodes if n != self.owner_node))

    @property
    def acceptance_authority(self) -> str:
        """Reserved decisions go to the Board (AR-BRD-003); otherwise the owner team accepts."""
        return "board" if self.reserved_decision else f"team_owner:{self.owner_node}"


@dataclass(frozen=True)
class MatchBreakdown:
    node: float
    knowledge: float
    domain: float

    @property
    def score(self) -> float:
        return round(W_NODE * self.node + W_KNOWLEDGE * self.knowledge + W_DOMAIN * self.domain, 4)

    def to_dict(self) -> dict[str, float]:
        return {"node": round(self.node, 4), "knowledge": round(self.knowledge, 4), "domain": round(self.domain, 4)}


@dataclass(frozen=True)
class ExecutorMatch:
    executor_id: str
    display_name: str
    home_node: str
    node_role: NodeRole
    role: ReferralRole
    breakdown: MatchBreakdown
    matched_terms: tuple[str, ...]
    shared_documents: tuple[str, ...]
    capacity: str
    reasons: tuple[str, ...]

    @property
    def score(self) -> float:
        return self.breakdown.score

    @property
    def eligible(self) -> bool:
        return self.role in {ReferralRole.LEAD_CANDIDATE, ReferralRole.COLLABORATOR}

    def to_dict(self) -> dict[str, object]:
        return {
            "executor_id": self.executor_id, "name": self.display_name, "home_node": self.home_node,
            "node_role": self.node_role.value, "role": self.role.value, "score": self.score,
            "breakdown": self.breakdown.to_dict(), "matched_terms": list(self.matched_terms),
            "shared_documents": list(self.shared_documents), "capacity": self.capacity, "reasons": list(self.reasons),
        }


@dataclass
class ReferralPlan:
    request: ReferralRequest
    matches: list[ExecutorMatch] = field(default_factory=list)

    @property
    def recommended(self) -> list[ExecutorMatch]:
        return [m for m in self.matches if m.eligible]

    @property
    def lead(self) -> ExecutorMatch | None:
        return next((m for m in self.matches if m.role is ReferralRole.LEAD_CANDIDATE), None)

    @property
    def collaborators(self) -> list[ExecutorMatch]:
        lead = self.lead
        return [m for m in self.recommended if lead is None or m.executor_id != lead.executor_id]

    @property
    def cross_node_candidates(self) -> list[ExecutorMatch]:
        return [m for m in self.matches if m.role is ReferralRole.CROSS_NODE_CANDIDATE]

    @property
    def excluded(self) -> list[ExecutorMatch]:
        return [m for m in self.matches if m.role is ReferralRole.EXCLUDED]

    def match_for(self, executor_id: str) -> ExecutorMatch:
        for m in self.matches:
            if m.executor_id == executor_id:
                return m
        raise KeyError(executor_id)

    def recommended_ids(self) -> list[str]:
        return [m.executor_id for m in self.recommended]

    def to_dict(self) -> dict[str, object]:
        lead = self.lead
        return {
            "item_id": self.request.item_id,
            "owner_node": self.request.owner_node,
            "acceptance_authority": self.request.acceptance_authority,
            "lead": lead.executor_id if lead else None,
            "collaborators": [m.executor_id for m in self.collaborators],
            "cross_node_candidates": [m.executor_id for m in self.cross_node_candidates],
            "matches": [m.to_dict() for m in self.matches],
        }


@dataclass(frozen=True)
class ExecutorMatcher:
    min_terms: int = MIN_TERMS
    full_terms: int = FULL_TERMS
    supporting_weight: float = SUPPORTING_NODE_WEIGHT

    def __post_init__(self) -> None:
        if self.min_terms < 2:
            raise InvariantError("a single matching keyword is insufficient (AR-EXE-023): min_terms must be >= 2")
        if self.full_terms < self.min_terms:
            raise InvariantError("full_terms must be >= min_terms")

    def evaluate(self, executor: Executor, request: ReferralRequest, request_terms: frozenset[str] | None = None) -> ExecutorMatch:
        req_terms = terms(request.text) if request_terms is None else request_terms
        profile = ExpertiseProfile.of(executor)
        home = str(executor.home_node)
        if home == request.owner_node:
            node_role, node_w = NodeRole.OWNER, 1.0
        elif home in request.supporting_nodes:
            node_role, node_w = NodeRole.SUPPORTING, self.supporting_weight
        else:
            node_role, node_w = NodeRole.NONE, 0.0
        item_docs = list(dict.fromkeys(request.related_documents))
        shared = tuple(d for d in item_docs if executor.holds(d))
        knowledge = len(shared) / len(item_docs) if item_docs else 0.0
        matched = profile.matched(req_terms)
        domain = min(len(matched), self.full_terms) / self.full_terms
        domain_ok = len(matched) >= self.min_terms

        reasons: list[str] = []
        if node_role is NodeRole.OWNER:
            reasons.append(f"home node {home} is the owner node")
        elif node_role is NodeRole.SUPPORTING:
            reasons.append(f"home node {home} is a supporting node")
        else:
            reasons.append(f"home node {home} is not one of the item's nodes")
        if not matched:
            reasons.append("no profile term occurs in the item")
        elif not domain_ok:
            reasons.append(f"a single matching term ({matched[0]}) is not enough")
        else:
            reasons.append("matched terms: " + ", ".join(matched))
        reasons.append("shares knowledge: " + ", ".join(shared) if shared else "no shared knowledge document")

        if executor.capacity.is_published and executor.capacity.hours_per_week == 0:
            role = ReferralRole.EXCLUDED
            reasons.append("no referral capacity (0 h/week)")
        elif node_role is NodeRole.OWNER and domain_ok:
            role = ReferralRole.LEAD_CANDIDATE
        elif node_role is NodeRole.SUPPORTING and (domain_ok or shared):
            role = ReferralRole.COLLABORATOR
        elif node_role is NodeRole.NONE and domain_ok and shared:
            role = ReferralRole.CROSS_NODE_CANDIDATE
            reasons.append("outside the item's nodes: the team owner decides")
        else:
            role = ReferralRole.EXCLUDED
            if node_role is NodeRole.NONE:
                reasons.append("excluded: not in the item's nodes")
            else:
                reasons.append("excluded: outside the allowed referral domain for this item")
        if not executor.capacity.is_published:
            reasons.append("capacity allocated through unit planning (neither zero nor unlimited)")
        return ExecutorMatch(
            str(executor.identifier), executor.display_name, home, node_role, role,
            MatchBreakdown(node_w, knowledge, domain), matched, shared, executor.capacity.describe(), tuple(reasons),
        )

    def plan(self, executors: list[Executor], request: ReferralRequest) -> ReferralPlan:
        req_terms = terms(request.text)
        matches = [self.evaluate(e, request, req_terms) for e in executors]
        matches.sort(key=lambda m: (-m.score, -len(m.matched_terms), m.executor_id))
        return ReferralPlan(request, matches)
