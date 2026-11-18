"""Executor aggregate, expertise tags, referral capacity and name aliases."""

from __future__ import annotations

from dataclasses import dataclass, field

from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.events import DomainEvent
from rag_core.shared_kernel.identifiers import ExecutorId, NodeIdentifier


@dataclass(frozen=True)
class ExpertiseTag:
    value: str

    def __post_init__(self) -> None:
        text = self.value.strip().lower()
        if not text:
            raise InvariantError("empty expertise tag")
        object.__setattr__(self, "value", text)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class ReferralCapacity:
    hours_per_week: int

    def __post_init__(self) -> None:
        if self.hours_per_week < 0 or self.hours_per_week > 60:
            raise InvariantError(f"referral hours out of range: {self.hours_per_week}")


# Canonical Latin spelling used in the executor registry (finding D2).
NAME_ALIASES: dict[str, str] = {
    "roozbeh mohseni": "Roozbeh Mohseni",
    "rouzbeh mohseni": "Roozbeh Mohseni",
}


def canonical_person_name(name: str) -> str:
    key = " ".join(name.split()).lower()
    return NAME_ALIASES.get(key, " ".join(name.split()))


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
    events: list[DomainEvent] = field(default_factory=list)

    def __post_init__(self) -> None:
        object.__setattr__(self, "display_name", canonical_person_name(self.display_name))
        if not self.display_name:
            raise InvariantError("executor name is required")

    def may_handle(self, issue_domain: str) -> bool:
        domain = issue_domain.strip().lower()
        allowed = {d.strip().lower() for d in self.allowed_referral_domains}
        return domain in allowed


def suggest_executors(candidates: list[Executor], issue_domain: str) -> list[Executor]:
    """Exclude anyone outside the allowed referral domain (policy item 11)."""
    return [c for c in candidates if c.may_handle(issue_domain)]
