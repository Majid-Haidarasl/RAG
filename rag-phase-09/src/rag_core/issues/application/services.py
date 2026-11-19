"""Phase 7 use cases: register / compare / decompose / position issues."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rag_core.issues.domain.comparison import ComparisonResult, IssueComparator, MatchLabel
from rag_core.issues.domain.decomposition import RuleBasedDecomposer, SubIssueDraft
from rag_core.issues.domain.model import Issue, RelativePosition
from rag_core.issues.domain.ports import IssueDecomposer, OrgDirectory
from rag_core.issues.domain.validation import IssueRegistryValidator, IssueValidationReport
from rag_core.issues.infrastructure.memory import InMemoryIssueRepository
from rag_core.issues.infrastructure.registry_json import JsonIssueRegistry
from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.events import DomainEvent


def corpus_document_ids() -> set[str]:
    from rag_core.ingestion.domain.catalog import CATALOG

    return set(CATALOG)


@dataclass
class LoadedIssues:
    issues: list[Issue]
    report: IssueValidationReport
    samples: list[dict]


def load_issue_registry(directory: Path, org: OrgDirectory) -> LoadedIssues:
    """Validate raw records first; only a clean registry becomes aggregates."""
    registry = JsonIssueRegistry(directory)
    records = registry.records()
    report = IssueRegistryValidator(org, corpus_document_ids()).validate(records)
    issues = registry.load(records) if report.ok else []
    return LoadedIssues(issues, report, registry.samples())


@dataclass
class IntakeOutcome:
    issue: Issue
    comparison: ComparisonResult
    registered: bool
    position: RelativePosition


class IssueService:
    def __init__(
        self,
        repository: InMemoryIssueRepository,
        directory: OrgDirectory,
        comparator: IssueComparator | None = None,
        decomposer: IssueDecomposer | None = None,
    ) -> None:
        self.repo = repository
        self.directory = directory
        self.comparator = comparator or IssueComparator()
        self.decomposer = decomposer or RuleBasedDecomposer(directory=directory)
        self.events: list[DomainEvent] = []

    def compare(self, issue: Issue) -> ComparisonResult:
        return self.comparator.compare(issue, self.repo.all())

    def intake(self, issue: Issue, *, register_duplicates: bool = False) -> IntakeOutcome:
        """Validate nodes, compare with existing issues, register unless it is a duplicate."""
        issue.assert_nodes_exist(self.directory)
        if self.repo.exists(issue.identifier):
            raise InvariantError(f"{issue.identifier} already exists")
        result = self.compare(issue)
        registered = result.label is not MatchLabel.DUPLICATE or register_duplicates
        if registered:
            if result.label is MatchLabel.RELATED and result.best is not None:
                best_root = result.best.key.split("/")[0]
                if best_root not in {str(r) for r in issue.related_issues}:
                    from rag_core.shared_kernel.identifiers import IssueId

                    issue.related_issues = (*issue.related_issues, IssueId(best_root))
            self.repo.save(issue)
            self.events.append(DomainEvent("IssueRegistered", {"issue_id": str(issue.identifier), "label": result.label.value}))
        else:
            self.events.append(
                DomainEvent("DuplicateIssueDetected", {"issue_id": str(issue.identifier), "duplicate_of": result.best.key if result.best else ""})
            )
        return IntakeOutcome(issue, result, registered, issue.relative_position(self.directory))

    def plan_subissues(self, issue: Issue) -> list[SubIssueDraft]:
        return self.decomposer.decompose(issue)

    def decompose(self, issue: Issue) -> list:
        drafts = self.plan_subissues(issue)
        return RuleBasedDecomposer(directory=self.directory).apply(issue, drafts)

    def position(self, issue: Issue) -> RelativePosition:
        return issue.relative_position(self.directory)
