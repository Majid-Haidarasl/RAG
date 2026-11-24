"""What a TransferPackage carries upward: work items, their issue context and capacity.

A ``TransferItem`` is one issue or sub-issue as seen by one node: the owner
node reports it with role ``owner``, a supporting node with role ``support``.
Items are value objects copied out of the issues / executors / IKE contexts by
the transfer ACL, so an upper layer never reaches back into a lower node's
issue list (context map, Phase 3).

* ``rank_items`` orders items deterministically: open before closed, reserved
  (Board) decisions first, blocked next, then priority, risk, status and id.
* ``merge_items`` removes duplicates that arrive from several children (the
  owner's copy wins over a supporter's copy).
* ``group_items`` groups sub-issues under their parent issue (used by the
  managerial and executive detail levels).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from rag_core.shared_kernel.errors import InvariantError

OPEN_STATUSES = frozenset({"open", "triaged", "in_progress", "blocked", "reopened"})
STATUS_RANK = {
    "blocked": 0,
    "reopened": 1,
    "in_progress": 2,
    "open": 3,
    "triaged": 3,
    "resolved": 5,
    "closed": 6,
}
PRIORITY_RANK = {"P1": 0, "P2": 1, "P3": 2, "P4": 3}


class ItemRole(StrEnum):
    OWNER = "owner"
    SUPPORT = "support"


@dataclass(frozen=True)
class IssueContext:
    """Facts of the (parent) issue an item belongs to."""

    issue_id: str
    title_en: str
    title_fa: str = ""
    status: str = ""
    priority: str = ""
    progress: int | None = None
    contract_ref: str = ""
    decision_amount_mtoman: int | None = None
    due_on: str = ""
    risk: int = 0
    customer: str = ""

    def __post_init__(self) -> None:
        if not self.issue_id.strip():
            raise InvariantError("issue context needs an issue id")
        if not self.title_en.strip():
            raise InvariantError(f"{self.issue_id}: issue context needs a title")

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "title_en": self.title_en,
            "title_fa": self.title_fa,
            "status": self.status,
            "priority": self.priority,
            "progress": self.progress,
            "contract_ref": self.contract_ref,
            "decision_amount_mtoman": self.decision_amount_mtoman,
            "due_on": self.due_on,
            "risk": self.risk,
            "customer": self.customer,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IssueContext:
        return cls(
            issue_id=str(data["issue_id"]),
            title_en=str(data["title_en"]),
            title_fa=str(data.get("title_fa", "")),
            status=str(data.get("status", "")),
            priority=str(data.get("priority", "")),
            progress=data.get("progress"),
            contract_ref=str(data.get("contract_ref", "")),
            decision_amount_mtoman=data.get("decision_amount_mtoman"),
            due_on=str(data.get("due_on", "")),
            risk=int(data.get("risk", 0)),
            customer=str(data.get("customer", "")),
        )


@dataclass(frozen=True)
class TransferItem:
    item_id: str
    title_en: str
    status: str
    owner_node: str
    origin_node: str
    title_fa: str = ""
    role: ItemRole = ItemRole.OWNER
    issue: IssueContext | None = None
    lead: str = ""
    lead_fa: str = ""
    collaborators: tuple[str, ...] = ()
    collaborators_fa: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()  # full item ids, e.g. ("AR-ISS-024/HW",)
    documents: tuple[str, ...] = ()
    gaps: tuple[str, ...] = ()  # knowledge-lack documents (Phase 9 IKE)
    acceptance_output: str = ""
    reserved_decision: bool = False
    priority: str = ""
    risk: int = 0

    def __post_init__(self) -> None:
        if not self.item_id.strip():
            raise InvariantError("transfer item needs an id")
        if not self.status.strip():
            raise InvariantError(f"{self.item_id}: transfer item needs a status")
        if not self.owner_node.strip() or not self.origin_node.strip():
            raise InvariantError(
                f"{self.item_id}: transfer item needs owner and origin nodes"
            )
        if not isinstance(self.role, ItemRole):
            object.__setattr__(self, "role", ItemRole(self.role))

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES

    @property
    def is_blocked(self) -> bool:
        return self.status == "blocked"

    @property
    def is_subissue(self) -> bool:
        return "/" in self.item_id

    @property
    def parent_id(self) -> str:
        if self.issue is not None:
            return self.issue.issue_id
        return self.item_id.split("/", 1)[0]

    @property
    def effective_priority(self) -> str:
        return self.priority or (self.issue.priority if self.issue else "")

    def rank_key(self) -> tuple[int, int, int, int, int, int, str]:
        return (
            0 if self.is_open else 1,
            0 if (self.reserved_decision and self.is_open) else 1,
            0 if self.is_blocked else 1,
            PRIORITY_RANK.get(self.effective_priority, 9),
            -self.risk,
            STATUS_RANK.get(self.status, 4),
            self.item_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "title_en": self.title_en,
            "title_fa": self.title_fa,
            "status": self.status,
            "owner_node": self.owner_node,
            "origin_node": self.origin_node,
            "role": self.role.value,
            "issue": self.issue.to_dict() if self.issue else None,
            "lead": self.lead,
            "lead_fa": self.lead_fa,
            "collaborators": list(self.collaborators),
            "collaborators_fa": list(self.collaborators_fa),
            "depends_on": list(self.depends_on),
            "documents": list(self.documents),
            "gaps": list(self.gaps),
            "acceptance_output": self.acceptance_output,
            "reserved_decision": self.reserved_decision,
            "priority": self.priority,
            "risk": self.risk,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TransferItem:
        issue = data.get("issue")
        return cls(
            item_id=str(data["item_id"]),
            title_en=str(data["title_en"]),
            status=str(data["status"]),
            owner_node=str(data["owner_node"]),
            origin_node=str(data["origin_node"]),
            title_fa=str(data.get("title_fa", "")),
            role=ItemRole(data.get("role", "owner")),
            issue=IssueContext.from_dict(issue) if issue else None,
            lead=str(data.get("lead", "")),
            lead_fa=str(data.get("lead_fa", "")),
            collaborators=tuple(data.get("collaborators", ())),
            collaborators_fa=tuple(data.get("collaborators_fa", ())),
            depends_on=tuple(data.get("depends_on", ())),
            documents=tuple(data.get("documents", ())),
            gaps=tuple(data.get("gaps", ())),
            acceptance_output=str(data.get("acceptance_output", "")),
            reserved_decision=bool(data.get("reserved_decision", False)),
            priority=str(data.get("priority", "")),
            risk=int(data.get("risk", 0)),
        )


def rank_items(
    items: list[TransferItem] | tuple[TransferItem, ...],
) -> list[TransferItem]:
    return sorted(items, key=lambda i: i.rank_key())


def merge_items(
    items: list[TransferItem] | tuple[TransferItem, ...],
) -> list[TransferItem]:
    """One copy per item id; the owner's copy wins over a supporter's, otherwise the first one."""
    chosen: dict[str, TransferItem] = {}
    for item in items:
        current = chosen.get(item.item_id)
        if current is None or (
            current.role is ItemRole.SUPPORT and item.role is ItemRole.OWNER
        ):
            chosen[item.item_id] = item
    return rank_items(list(chosen.values()))


@dataclass(frozen=True)
class IssueGroup:
    """Items of one parent issue (or one stand-alone issue item)."""

    issue: IssueContext
    items: tuple[TransferItem, ...]

    def __post_init__(self) -> None:
        if not self.items:
            raise InvariantError(
                f"{self.issue.issue_id}: an issue group needs at least one item"
            )

    @property
    def group_id(self) -> str:
        return self.issue.issue_id

    @property
    def is_parent(self) -> bool:
        """True when the group holds sub-issues; False for a stand-alone issue item."""
        return any(i.is_subissue for i in self.items)

    @property
    def item_ids(self) -> tuple[str, ...]:
        return tuple(i.item_id for i in self.items)

    @property
    def open_count(self) -> int:
        return sum(1 for i in self.items if i.is_open)

    @property
    def blocked_count(self) -> int:
        return sum(1 for i in self.items if i.is_blocked)

    @property
    def reserved_items(self) -> tuple[str, ...]:
        return tuple(i.item_id for i in self.items if i.reserved_decision and i.is_open)

    @property
    def owner_nodes(self) -> tuple[str, ...]:
        return tuple(sorted({i.owner_node for i in self.items}))

    def rank_key(self) -> tuple[int, int, int, int, int, int, str]:
        return min(i.rank_key() for i in self.items)


def _context_of(item: TransferItem) -> IssueContext:
    if item.issue is not None:
        return item.issue
    return IssueContext(
        item.parent_id,
        item.title_en,
        item.title_fa,
        item.status,
        item.priority,
        risk=item.risk,
    )


def group_items(
    items: list[TransferItem] | tuple[TransferItem, ...],
) -> list[IssueGroup]:
    buckets: dict[str, list[TransferItem]] = {}
    contexts: dict[str, IssueContext] = {}
    for item in items:
        key = item.parent_id
        buckets.setdefault(key, []).append(item)
        contexts.setdefault(key, _context_of(item))
    groups = [IssueGroup(contexts[k], tuple(rank_items(v))) for k, v in buckets.items()]
    return sorted(groups, key=lambda g: g.rank_key())


def single_groups(
    items: list[TransferItem] | tuple[TransferItem, ...],
) -> list[IssueGroup]:
    """One group per item (the ``items`` aggregation mode keeps every item on its own line)."""
    return [IssueGroup(_context_of(i), (i,)) for i in rank_items(items)]


@dataclass(frozen=True)
class ExecutorRef:
    executor_id: str
    name_en: str
    name_fa: str = ""
    hours_per_week: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "executor_id": self.executor_id,
            "name_en": self.name_en,
            "name_fa": self.name_fa,
            "hours_per_week": self.hours_per_week,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutorRef:
        return cls(
            str(data["executor_id"]),
            str(data["name_en"]),
            str(data.get("name_fa", "")),
            data.get("hours_per_week"),
        )


@dataclass(frozen=True)
class CapacitySummary:
    """Referral capacity (AR-EXE-023): published weekly hours versus unit planning."""

    executors: int = 0
    published: int = 0
    hours_per_week: int = 0
    unit_planning: tuple[str, ...] = ()  # names (English) without published hours
    people: tuple[ExecutorRef, ...] = field(default_factory=tuple)

    @classmethod
    def of(
        cls, executors: list[ExecutorRef] | tuple[ExecutorRef, ...]
    ) -> CapacitySummary:
        people = tuple(sorted(executors, key=lambda e: e.name_en))
        published = [e for e in people if e.hours_per_week is not None]
        return cls(
            executors=len(people),
            published=len(published),
            hours_per_week=sum(int(e.hours_per_week or 0) for e in published),
            unit_planning=tuple(e.name_en for e in people if e.hours_per_week is None),
            people=people,
        )

    def plus(self, other: CapacitySummary) -> CapacitySummary:
        return CapacitySummary(
            executors=self.executors + other.executors,
            published=self.published + other.published,
            hours_per_week=self.hours_per_week + other.hours_per_week,
            unit_planning=tuple(
                sorted(set(self.unit_planning) | set(other.unit_planning))
            ),
            people=tuple(
                sorted({*self.people, *other.people}, key=lambda e: e.name_en)
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "executors": self.executors,
            "published": self.published,
            "hours_per_week": self.hours_per_week,
            "unit_planning": list(self.unit_planning),
            "people": [p.to_dict() for p in self.people],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CapacitySummary:
        return cls(
            int(data.get("executors", 0)),
            int(data.get("published", 0)),
            int(data.get("hours_per_week", 0)),
            tuple(data.get("unit_planning", ())),
            tuple(ExecutorRef.from_dict(p) for p in data.get("people", ())),
        )


@dataclass(frozen=True)
class DocumentRef:
    document_id: str
    version: str

    def __str__(self) -> str:
        return f"{self.document_id}@{self.version}"


@dataclass(frozen=True)
class NodeKnowledge:
    """Everything a node may put into its package this cycle (built by the transfer ACL)."""

    node_id: str
    layer: int
    name_en: str
    name_fa: str = ""
    documents: tuple[DocumentRef, ...] = ()
    items: tuple[TransferItem, ...] = ()
    executors: tuple[ExecutorRef, ...] = ()

    def __post_init__(self) -> None:
        if not self.node_id.strip():
            raise InvariantError("node knowledge needs a node id")
        for item in self.items:
            if item.origin_node != self.node_id:
                raise InvariantError(
                    f"{item.item_id}: origin {item.origin_node} is not {self.node_id}"
                )
