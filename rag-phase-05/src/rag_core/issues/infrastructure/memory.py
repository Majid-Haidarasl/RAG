from __future__ import annotations

from rag_core.issues.domain.model import Issue
from rag_core.shared_kernel.errors import NotFoundError
from rag_core.shared_kernel.identifiers import IssueId


class InMemoryIssueRepository:
    def __init__(self) -> None:
        self._items: dict[str, Issue] = {}

    def get(self, issue_id: IssueId) -> Issue:
        item = self._items.get(issue_id.value)
        if item is None:
            raise NotFoundError(str(issue_id))
        return item

    def save(self, issue: Issue) -> None:
        self._items[issue.identifier.value] = issue
