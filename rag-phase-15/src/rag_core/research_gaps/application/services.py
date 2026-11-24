"""Gap detection use case and the gap report."""

from __future__ import annotations

from dataclasses import dataclass, field

from rag_core.research_gaps.domain.model import Gap, GapInputs
from rag_core.research_gaps.domain.rules import RULE_ORDER, GapRuleBook


@dataclass
class GapReport:
    gaps: list[Gap] = field(default_factory=list)

    def by_rule(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for code in RULE_ORDER:
            n = sum(1 for g in self.gaps if g.rule == code)
            if n:
                out[code] = n
        return out

    def by_severity(self) -> dict[str, int]:
        out = {"high": 0, "medium": 0, "low": 0}
        for g in self.gaps:
            out[g.severity.value] += 1
        return out

    def by_kind(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for g in self.gaps:
            out[g.kind.value] = out.get(g.kind.value, 0) + 1
        return out

    def for_issue(self, issue_id: str) -> list[Gap]:
        """Gaps on the issue itself or on one of its sub-issues."""
        return [
            g
            for g in self.gaps
            if g.issue_id == issue_id
            or g.subject == issue_id
            or g.subject.startswith(issue_id + "/")
        ]

    def count_by_issue(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for g in self.gaps:
            issue = g.issue_id or (
                g.subject.split("/", 1)[0] if g.subject.startswith("AR-ISS-") else ""
            )
            if issue:
                out[issue] = out.get(issue, 0) + 1
        return out

    def to_dict(self) -> dict[str, object]:
        return {
            "total": len(self.gaps),
            "by_rule": self.by_rule(),
            "by_severity": self.by_severity(),
            "by_kind": self.by_kind(),
            "gaps": [g.to_dict() for g in self.gaps],
        }


class GapService:
    def __init__(self, rulebook: GapRuleBook | None = None) -> None:
        self.rulebook = rulebook or GapRuleBook()

    def detect(self, inputs: GapInputs) -> GapReport:
        return GapReport(self.rulebook.detect(inputs))
