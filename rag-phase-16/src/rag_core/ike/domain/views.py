"""What the IKE context knows about issues and referrals (filled by ACLs).

IKE does not own issues, executors or knowledge: it only relates them.
These read-only views are translated from the issues and executors
contexts in ``ike.infrastructure``.
"""

from __future__ import annotations

from dataclasses import dataclass

from rag_core.shared_kernel.errors import InvariantError


@dataclass(frozen=True)
class SubItemView:
    item_id: str
    code: str
    title: str
    owner_node: str
    status: str
    title_fa: str = ""
    scope: str = ""
    supporting_nodes: tuple[str, ...] = ()
    related_documents: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()  # sibling codes
    acceptance_output: str = ""
    reserved_decision: bool = False

    def __post_init__(self) -> None:
        if "/" not in self.item_id or not self.owner_node:
            raise InvariantError(f"sub-item {self.item_id!r} needs a parent/CODE id and an owner node")

    @property
    def parent_id(self) -> str:
        return self.item_id.split("/", 1)[0]

    @property
    def query(self) -> str:
        """Bilingual retrieval query: English title + scope, Persian title."""
        return " ".join(p for p in (self.title, self.scope, self.title_fa) if p)


@dataclass(frozen=True)
class IssueView:
    issue_id: str
    title: str
    owner_node: str
    status: str
    progress_percent: int
    title_fa: str = ""
    customer: str = ""
    contract_ref: str = ""
    related_documents: tuple[str, ...] = ()
    reserved_decision: bool = False
    sub_items: tuple[SubItemView, ...] = ()

    def sub_item(self, code: str) -> SubItemView:
        for s in self.sub_items:
            if s.code == code:
                return s
        raise KeyError(code)


@dataclass(frozen=True)
class ReferralView:
    """One recommended executor for one work item (from the executors context)."""

    item_id: str
    executor_id: str
    name: str
    role: str  # "lead" | "collaborator"
    score: float
    knowledge_documents: tuple[str, ...] = ()
    name_fa: str = ""

    def __post_init__(self) -> None:
        if self.role not in {"lead", "collaborator"}:
            raise InvariantError(f"referral role must be lead or collaborator, got {self.role!r}")
