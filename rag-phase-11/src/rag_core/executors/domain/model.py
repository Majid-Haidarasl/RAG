"""Executor aggregate, expertise tags, referral capacity and name aliases.

Phase 3 defined the skeleton (identity, home team, allowed referral domain).
Phase 9 adds the profile metadata of AR-EXE-023: bilingual name and role,
specialty, expertise tags, authoritative knowledge documents, outputs,
authority limits and the weekly referral ceiling. Pay is never stored here
(AR-EXE-023 keeps it access-restricted and matching does not need it).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.events import DomainEvent
from rag_core.shared_kernel.identifiers import DocumentId, ExecutorId, NodeIdentifier

MAX_REFERRAL_HOURS = 60


@dataclass(frozen=True)
class ExpertiseTag:
    value: str

    def __post_init__(self) -> None:
        text = " ".join(self.value.split()).lower()
        if not text:
            raise InvariantError("empty expertise tag")
        object.__setattr__(self, "value", text)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class ReferralCapacity:
    """Weekly referral ceiling (AR-EXE-023 §1), not employment hours.

    ``None`` means "no fixed hours published; allocated through unit
    planning". That is neither zero nor unlimited capacity.
    """

    hours_per_week: int | None

    def __post_init__(self) -> None:
        if self.hours_per_week is None:
            return
        if self.hours_per_week < 0 or self.hours_per_week > MAX_REFERRAL_HOURS:
            raise InvariantError(f"referral hours out of range: {self.hours_per_week}")

    @property
    def is_published(self) -> bool:
        return self.hours_per_week is not None

    @classmethod
    def unpublished(cls) -> ReferralCapacity:
        return cls(None)

    def describe(self) -> str:
        if self.hours_per_week is None:
            return "unit planning (no fixed hours published)"
        return f"{self.hours_per_week} h/week"


# Canonical Latin spelling used in the executor registry (finding D2).
NAME_ALIASES: dict[str, str] = {
    "roozbeh mohseni": "Roozbeh Mohseni",
    "rouzbeh mohseni": "Roozbeh Mohseni",
}


def canonical_person_name(name: str) -> str:
    key = " ".join(name.split()).lower()
    return NAME_ALIASES.get(key, " ".join(name.split()))


def executor_id_for(name: str) -> ExecutorId:
    """``Roozbeh Mohseni`` → ``EX-ROOZBEH-MOHSENI`` (after alias normalization)."""
    return ExecutorId("EX-" + "-".join(canonical_person_name(name).upper().split()))


@dataclass
class Executor:
    """A person (or named capability holder), not a Node.

    A team node may be a referral *target*, but it is not an Executor.
    The shared kernel between the two contexts is only NodeIdentifier
    (home team).
    """

    identifier: ExecutorId
    display_name: str
    home_node: NodeIdentifier
    expertise: tuple[ExpertiseTag, ...]
    allowed_referral_domains: tuple[str, ...]
    capacity: ReferralCapacity
    # ---- Phase 9 profile metadata (AR-EXE-023)
    name_fa: str = ""
    role: str = ""
    role_fa: str = ""
    specialty: tuple[str, ...] = ()
    knowledge_documents: tuple[DocumentId, ...] = ()
    outputs: tuple[str, ...] = ()
    authority_limits: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    profile_version: str = "1.0"
    source_document: str = "AR-EXE-023"
    events: list[DomainEvent] = field(default_factory=list)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "display_name", canonical_person_name(self.display_name)
        )
        if not self.display_name:
            raise InvariantError("executor name is required")
        if len(set(self.knowledge_documents)) != len(self.knowledge_documents):
            raise InvariantError(f"duplicate knowledge documents for {self.identifier}")

    def may_handle(self, issue_domain: str) -> bool:
        domain = issue_domain.strip().lower()
        allowed = {d.strip().lower() for d in self.allowed_referral_domains}
        return domain in allowed

    def answers_to(self, name: str) -> bool:
        """True for the display name or a registered alias (any spacing/case)."""
        wanted = " ".join(canonical_person_name(name).split()).lower()
        names = {
            self.display_name.lower(),
            *(" ".join(a.split()).lower() for a in self.aliases),
        }
        names |= {canonical_person_name(a).lower() for a in self.aliases}
        return wanted in names

    def holds(self, document_id: str) -> bool:
        return any(str(d) == document_id for d in self.knowledge_documents)

    def change_capacity(
        self, capacity: ReferralCapacity, *, reason: str, approved_by: str
    ) -> None:
        """AR-EXE-023 §3: a ceiling never changes silently; reason, version and approval are required."""
        if not reason.strip():
            raise InvariantError("a profile change needs a reason")
        if not approved_by.strip():
            raise InvariantError("a profile change needs team-owner approval")
        old = self.capacity
        self.capacity = capacity
        major, _, minor = self.profile_version.partition(".")
        self.profile_version = f"{major}.{int(minor or 0) + 1}"
        self.events.append(
            DomainEvent(
                "ExecutorProfileChanged",
                {
                    "executor_id": str(self.identifier),
                    "field": "capacity",
                    "old": old.hours_per_week,
                    "new": capacity.hours_per_week,
                    "reason": reason,
                    "approved_by": approved_by,
                    "version": self.profile_version,
                },
            )
        )


def suggest_executors(candidates: list[Executor], issue_domain: str) -> list[Executor]:
    """Exclude anyone outside the allowed referral domain (policy item 11)."""
    return [c for c in candidates if c.may_handle(issue_domain)]
