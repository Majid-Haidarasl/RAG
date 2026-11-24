"""Phase 9 use cases: load the executor registry, match work items, analyse load."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from rag_core.executors.domain.matching import (
    ExecutorMatcher,
    ReferralPlan,
    ReferralRequest,
    ReferralRole,
)
from rag_core.executors.domain.model import Executor
from rag_core.executors.domain.ports import TeamDirectory
from rag_core.executors.domain.validation import (
    ExecutorRegistryValidator,
    ExecutorValidationReport,
)
from rag_core.executors.infrastructure.memory import InMemoryExecutorRepository
from rag_core.executors.infrastructure.registry_json import JsonExecutorRegistry
from rag_core.shared_kernel.errors import NotFoundError


def corpus_document_ids() -> set[str]:
    from rag_core.ingestion.domain.catalog import CATALOG

    return set(CATALOG)


@dataclass
class LoadedExecutors:
    executors: list[Executor]
    report: ExecutorValidationReport

    def repository(self) -> InMemoryExecutorRepository:
        return InMemoryExecutorRepository(self.executors)


def load_executor_registry(directory: Path, teams: TeamDirectory) -> LoadedExecutors:
    """Validate raw records first; only a clean registry becomes aggregates."""
    registry = JsonExecutorRegistry(directory)
    records = registry.records()
    report = ExecutorRegistryValidator(teams, corpus_document_ids()).validate(records)
    return LoadedExecutors(registry.load(records) if report.ok else [], report)


@dataclass(frozen=True)
class SeedComparison:
    """Matcher output vs the executors the team owner named in the issue registry."""

    item_id: str
    named: tuple[str, ...]
    resolved: tuple[str, ...]
    unresolved: tuple[str, ...]
    recommended: tuple[str, ...]

    @property
    def agrees(self) -> bool:
        return not self.unresolved and set(self.resolved) == set(self.recommended)

    @property
    def true_positives(self) -> int:
        return len(set(self.resolved) & set(self.recommended))

    def to_dict(self) -> dict[str, object]:
        return {
            "item_id": self.item_id,
            "named": list(self.named),
            "resolved": list(self.resolved),
            "unresolved": list(self.unresolved),
            "recommended": list(self.recommended),
            "agrees": self.agrees,
        }


@dataclass
class ExecutorLoad:
    executor_id: str
    name: str
    home_node: str
    capacity: str
    lead: list[str] = field(default_factory=list)
    collaborator: list[str] = field(default_factory=list)

    @property
    def referrals(self) -> int:
        return len(self.lead) + len(self.collaborator)

    def to_dict(self) -> dict[str, object]:
        return {
            "executor_id": self.executor_id,
            "name": self.name,
            "home_node": self.home_node,
            "capacity": self.capacity,
            "lead": self.lead,
            "collaborator": self.collaborator,
            "referrals": self.referrals,
        }


class ExecutorMatchingService:
    def __init__(
        self,
        repository: InMemoryExecutorRepository,
        matcher: ExecutorMatcher | None = None,
    ) -> None:
        self.repo = repository
        self.matcher = matcher or ExecutorMatcher()

    def plan(self, request: ReferralRequest) -> ReferralPlan:
        return self.matcher.plan(self.repo.list_all(), request)

    def plans(self, requests: list[ReferralRequest]) -> list[ReferralPlan]:
        return [self.plan(r) for r in requests]

    def resolve_names(self, names: tuple[str, ...]) -> tuple[list[str], list[str]]:
        resolved: list[str] = []
        unresolved: list[str] = []
        for name in names:
            try:
                resolved.append(str(self.repo.by_name(name).identifier))
            except NotFoundError:
                unresolved.append(name)
        return resolved, unresolved

    def compare_with_seed(self, plan: ReferralPlan) -> SeedComparison:
        resolved, unresolved = self.resolve_names(plan.request.named_executors)
        return SeedComparison(
            plan.request.item_id,
            plan.request.named_executors,
            tuple(resolved),
            tuple(unresolved),
            tuple(plan.recommended_ids()),
        )

    def load(self, plans: list[ReferralPlan]) -> list[ExecutorLoad]:
        """Referrals per executor across plans (lead / collaborator), registry order."""
        rows = {
            str(e.identifier): ExecutorLoad(
                str(e.identifier),
                e.display_name,
                str(e.home_node),
                e.capacity.describe(),
            )
            for e in self.repo.list_all()
        }
        for plan in plans:
            lead = plan.lead
            if lead is not None:
                rows[lead.executor_id].lead.append(plan.request.item_id)
            for m in plan.collaborators:
                rows[m.executor_id].collaborator.append(plan.request.item_id)
        return list(rows.values())


def role_counts(plans: list[ReferralPlan]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for plan in plans:
        for m in plan.matches:
            counts[m.role.value] += 1
    return {r.value: counts.get(r.value, 0) for r in ReferralRole}
