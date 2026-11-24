"""Phase 12 test helpers: small synthetic projects, records, signals and the shipped registries."""

from __future__ import annotations

import copy
from functools import lru_cache
import json
from pathlib import Path

from rag_core.projects.domain.model import (
    Project,
    ProjectRegistry,
    ScorecardDimension,
    TrackRecord,
)
from rag_core.projects.domain.validation import IssueFacts
from rag_core.prioritization.domain.model import Caps, IssueSignal, Weights
from rag_core.research_gaps.domain.model import (
    DimensionView,
    GapInputs,
    IssueStateView,
    RecordView,
    SubIssueView,
)

REPO = Path(__file__).resolve().parents[3]
PROJECTS_DIR = REPO / "data" / "projects"
CONFIG = REPO / "config" / "projects.yaml"

WEIGHTS = {
    "priority": 0.15,
    "severity": 0.10,
    "urgency": 0.15,
    "risk": 0.15,
    "dependents": 0.10,
    "exposure": 0.10,
    "blocked": 0.10,
    "gaps": 0.10,
    "spread": 0.05,
}
NODES = {"N-BRD", "N-CEO", "N-HW", "N-SW", "N-HW-REP", "N-SW-WEB", "N-SW-WIN", "N-LIB"}
DOCS = {"AR-TRN-026", "AR-FIN-008", "AR-ISS-024", "AR-HW-012"}
ISSUES = {
    "AR-ISS-024": IssueFacts("AR-ISS-024", "in_progress", 8, 2),
    "AR-ISS-031": IssueFacts("AR-ISS-031", "triaged", 5, 0),
    "AR-ISS-034": IssueFacts("AR-ISS-034", "closed", 2, 0),
}


def project(**changes: object) -> Project:
    base: dict[str, object] = dict(
        project_id="PRJ-AZP-118",
        name_en="Azarpakhsh warehouse system",
        name_fa="سامانه انبار آذرپخش",
        owner_node="N-CEO",
        progress_percent=62,
        status="at_risk",
        nodes=("N-HW-REP", "N-SW-WEB"),
        contract_value_mtoman=2180,
        remaining_mtoman=1240,
        primary_issue="AR-ISS-024",
        issues=("AR-ISS-024",),
        evidence=("AR-TRN-026", "AR-FIN-008"),
    )
    base.update(changes)
    return Project(**base)  # type: ignore[arg-type]


def record(
    record_id: str = "ACH-IKE-PATH", kind: str = "achievement", **changes: object
) -> TrackRecord:
    base: dict[str, object] = dict(
        record_id=record_id,
        kind=kind,
        state="recorded",
        title_en="Explicit path",
        title_fa="مسیر صریح",
        statement_en="The cycle created a path for AR-ISS-024.",
        statement_fa="این چرخه برای AR-ISS-024 مسیر ساخت.",
        conditions="Recorded for one case only.",
        nodes=("N-LIB",),
        evidence=("AR-TRN-026",),
    )
    if kind == "research":
        base.update(
            state="open",
            people=("Saeed Akbari",),
            nodes=("N-HW-REP",),
            risks=("lighting",),
            evidence_needed=("healthy and faulty examples",),
            conditions="Triage assistance only.",
        )
    if kind == "unsolved_issue":
        base.update(state="open", issues=("AR-ISS-024",))
    if kind == "challenge":
        base.update(state="open")
    base.update(changes)
    return TrackRecord(**base)  # type: ignore[arg-type]


def registry(
    *records: TrackRecord,
    projects: tuple[Project, ...] | None = None,
    scorecard: tuple[ScorecardDimension, ...] = (),
) -> ProjectRegistry:
    return ProjectRegistry(
        "1403-Q2",
        "1403-06-31",
        projects if projects is not None else (project(),),
        tuple(records),
        scorecard,
    )


def raw_registry() -> dict:
    return copy.deepcopy(_raw())


@lru_cache(maxsize=1)
def _raw() -> dict:
    return json.loads(
        (PROJECTS_DIR / "project-registry.json").read_text(encoding="utf-8")
    )


def signal(issue_id: str = "AR-ISS-024", **changes: object) -> IssueSignal:
    base: dict[str, object] = dict(
        issue_id=issue_id,
        title_en=f"Issue {issue_id}",
        title_fa="مسئله",
        status="in_progress",
        priority="P2",
        severity="high",
        urgency=8,
        risk=8,
        dependents=4,
        exposure_mtoman=1240,
        subissues=4,
        blocked_subissues=2,
        gaps=4,
        affected_nodes=7,
        progress=62,
    )
    base.update(changes)
    return IssueSignal(**base)  # type: ignore[arg-type]


def shipped_like_signals() -> list[IssueSignal]:
    """The five open shipped issues as the Phase 12 ACL sees them (4 gaps on AR-ISS-024)."""
    return [
        signal("AR-ISS-024"),
        signal(
            "AR-ISS-031",
            status="triaged",
            priority="P3",
            severity="medium",
            urgency=5,
            risk=5,
            dependents=1,
            exposure_mtoman=225,
            subissues=0,
            blocked_subissues=0,
            gaps=0,
            affected_nodes=2,
            progress=None,
        ),
        signal(
            "AR-ISS-032",
            status="open",
            priority="P3",
            severity="medium",
            urgency=4,
            risk=6,
            dependents=0,
            exposure_mtoman=0,
            subissues=0,
            blocked_subissues=0,
            gaps=0,
            affected_nodes=1,
            progress=None,
        ),
        signal(
            "AR-ISS-033",
            status="in_progress",
            priority="P4",
            severity="low",
            urgency=2,
            risk=2,
            dependents=0,
            exposure_mtoman=410,
            subissues=0,
            blocked_subissues=0,
            gaps=0,
            affected_nodes=1,
            progress=None,
        ),
        signal(
            "AR-ISS-035",
            status="triaged",
            priority="P3",
            severity="medium",
            urgency=5,
            risk=4,
            dependents=1,
            exposure_mtoman=0,
            subissues=0,
            blocked_subissues=0,
            gaps=0,
            affected_nodes=2,
            progress=None,
        ),
        signal(
            "AR-ISS-034",
            status="closed",
            priority="P3",
            severity="medium",
            urgency=3,
            risk=2,
            dependents=0,
            exposure_mtoman=0,
            subissues=0,
            blocked_subissues=0,
            gaps=0,
            affected_nodes=1,
            progress=None,
        ),
        signal(
            "AR-ISS-036",
            status="closed",
            priority="P2",
            severity="medium",
            urgency=5,
            risk=4,
            dependents=0,
            exposure_mtoman=0,
            subissues=0,
            blocked_subissues=0,
            gaps=0,
            affected_nodes=2,
            progress=None,
            duplicate_of="AR-ISS-024",
        ),
    ]


def weights() -> Weights:
    return Weights(WEIGHTS)


def caps() -> Caps:
    return Caps()


def sub(item_id: str, status: str = "in_progress", **changes: object) -> SubIssueView:
    base: dict[str, object] = dict(
        item_id=item_id,
        issue_id=item_id.split("/")[0],
        title_en=f"Work {item_id}",
        title_fa="کار",
        status=status,
        owner_node="N-HW-REP",
        executors=("Saeed Akbari",),
        lead="EX-SAEED-AKBARI",
    )
    base.update(changes)
    return SubIssueView(**base)  # type: ignore[arg-type]


def rec_view(
    record_id: str, kind: str, state: str = "open", **changes: object
) -> RecordView:
    base: dict[str, object] = dict(
        record_id=record_id,
        kind=kind,
        state=state,
        title_en=f"Record {record_id}",
        title_fa="رکورد",
        evidence=("AR-TRN-026",),
    )
    base.update(changes)
    return RecordView(**base)  # type: ignore[arg-type]


def gap_inputs(**changes: object) -> GapInputs:
    base: dict[str, object] = dict(
        records=(
            rec_view("RES-PHOTO-TRIAGE", "research"),
            rec_view("CHL-KEY-CAPACITY", "challenge"),
            rec_view("CHL-JOINT-SCHED", "challenge", issues=("AR-ISS-024",)),
            rec_view("UNS-AZP-DELAY", "unsolved_issue", issues=("AR-ISS-024",)),
        ),
        subissues=(
            sub("AR-ISS-024/HW", lacks=("AR-HW-013",)),
            sub(
                "AR-ISS-024/WIN",
                "blocked",
                depends_on=("AR-ISS-024/HW",),
                lacks=("AR-SW-019",),
            ),
            sub("AR-ISS-024/WEB"),
        ),
        issues=(
            IssueStateView("AR-ISS-024", "in_progress"),
            IssueStateView("AR-ISS-034", "closed"),
        ),
        scorecard=(
            DimensionView("SC-REF", "Referral coverage", "پوشش ارجاع", "recorded"),
            DimensionView("SC-CAP", "Capacity control", "کنترل ظرفیت", "conditional"),
            DimensionView(
                "SC-RRQ",
                "Repair retrieval quality",
                "کیفیت بازیابی تعمیر",
                "open",
                research="RES-RETRIEVAL-EVAL",
            ),
        ),
    )
    base.update(changes)
    return GapInputs(**base)  # type: ignore[arg-type]
