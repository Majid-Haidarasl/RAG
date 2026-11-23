from __future__ import annotations

from typing import Protocol

from rag_core.issues.domain.model import Issue, ProjectRecord
from rag_core.shared_kernel.identifiers import IssueId, ProjectId


class IssueRepository(Protocol):
    def get(self, issue_id: IssueId) -> Issue: ...
    def save(self, issue: Issue) -> None: ...


class ProjectRecordRepository(Protocol):
    def get(self, project_id: ProjectId) -> ProjectRecord: ...
    def save(self, record: ProjectRecord) -> None: ...
