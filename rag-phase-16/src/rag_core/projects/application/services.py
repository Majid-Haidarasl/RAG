"""Project tracking use cases: overview per project and the tracking matrix."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from rag_core.projects.domain.model import RECORD_KINDS, ProjectRegistry, RecordKind
from rag_core.projects.domain.validation import IssueFacts, health


@dataclass(frozen=True)
class ProjectOverview:
    project_id: str
    name_en: str
    name_fa: str
    owner_node: str
    status: str
    health: str
    progress_percent: int
    remaining_mtoman: int | None
    contract_value_mtoman: int | None
    issues: int
    open_issues: int
    blocked_subissues: int
    records: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return dict(self.__dict__)


class ProjectTrackingService:
    def __init__(self, registry: ProjectRegistry, issues: Mapping[str, IssueFacts], *, risk_threshold: int = 7) -> None:
        self.registry = registry
        self.issues = dict(issues)
        self.risk_threshold = risk_threshold

    def overview(self) -> list[ProjectOverview]:
        rows: list[ProjectOverview] = []
        for p in self.registry.projects:
            linked = [self.issues[i] for i in p.issues if i in self.issues]
            counts = {k: len(self.registry.records_of(k, p.project_id)) for k in RECORD_KINDS}
            rows.append(ProjectOverview(
                project_id=p.project_id, name_en=p.name_en, name_fa=p.name_fa, owner_node=p.owner_node,
                status=p.status.value, health=health(linked, risk_threshold=self.risk_threshold),
                progress_percent=p.progress_percent, remaining_mtoman=p.remaining_mtoman,
                contract_value_mtoman=p.contract_value_mtoman, issues=len(p.issues),
                open_issues=sum(1 for i in linked if i.is_open),
                blocked_subissues=sum(i.blocked_subissues for i in linked if i.is_open), records=counts,
            ))
        return rows

    def matrix(self) -> dict[str, dict[str, int]]:
        """Project (or ``cycle`` for records without a project) x record kind -> count."""
        out: dict[str, dict[str, int]] = {}
        for r in self.registry.records:
            row = out.setdefault(r.project or "cycle", {k: 0 for k in RECORD_KINDS})
            row[r.kind.value] += 1
        return out

    def open_research(self) -> list[str]:
        return [r.record_id for r in self.registry.records_of(RecordKind.RESEARCH) if r.state.value != "recorded"]

    def remaining_total(self) -> int:
        return sum(p.remaining_mtoman or 0 for p in self.registry.projects)
