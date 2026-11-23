from __future__ import annotations

from rag_core.issues.domain.model import Issue
from rag_core.shared_kernel.errors import NotFoundError
from rag_core.shared_kernel.identifiers import IssueId


class InMemoryIssueRepository:
    def __init__(self, issues: list[Issue] | None = None) -> None:
        self._items: dict[str, Issue] = {}
        for issue in issues or []:
            self.save(issue)

    def get(self, issue_id: IssueId) -> Issue:
        item = self._items.get(issue_id.value)
        if item is None:
            raise NotFoundError(str(issue_id))
        return item

    def save(self, issue: Issue) -> None:
        self._items[issue.identifier.value] = issue

    def all(self) -> list[Issue]:
        return [self._items[k] for k in sorted(self._items)]

    def exists(self, issue_id: IssueId) -> bool:
        return issue_id.value in self._items
