"""Phase 11 test helpers: small synthetic nodes, items and drafts (no corpus files)."""

from __future__ import annotations

from dataclasses import dataclass

from rag_core.judging.domain.rubric import default_rubric
from rag_core.judging.domain.rule_judge import RuleBasedJudge
from rag_core.processing.domain.plan import ProcessingStep
from rag_core.qa.domain.fact_check import CitedFactValidator
from rag_core.transfer.domain.builder import PackageDraft, TransferPackageBuilder
from rag_core.transfer.domain.items import (
    DocumentRef,
    ExecutorRef,
    IssueContext,
    ItemRole,
    NodeKnowledge,
    TransferItem,
)
from rag_core.transfer.domain.levels import RuleBook
from rag_core.transfer.domain.review import BuiltPackage, PackageReviewer
from rag_core.transfer.infrastructure.judging_acl import CaseJudgeAdapter

CYCLE = "1403-Q2"
VERSIONS = {
    "AR-HW-012": "1.2",
    "AR-HW-013": "1.0",
    "AR-HW-015": "1.0",
    "AR-SW-019": "1.1",
    "AR-ISS-024": "1.0",
    "AR-ISS-031": "1.0",
    "AR-FIN-010": "1.0",
}

ISSUE_024 = IssueContext(
    issue_id="AR-ISS-024",
    title_en="Azarpakhsh delivery delay",
    title_fa="تأخیر تحویل آذرپخش",
    status="in_progress",
    priority="P1",
    progress=62,
    contract_ref="AR-RFP-025",
    decision_amount_mtoman=850,
    due_on="1403-07-15",
    risk=9,
    customer="Azarpakhsh",
)
ISSUE_031 = IssueContext(
    issue_id="AR-ISS-031",
    title_en="Mobile app login failures",
    title_fa="خطای ورود اپلیکیشن موبایل",
    status="triaged",
    priority="P3",
    risk=5,
)


def item(item_id: str, origin: str, **changes: object) -> TransferItem:
    base: dict[str, object] = dict(
        item_id=item_id,
        title_en=f"Work on {item_id}",
        status="in_progress",
        owner_node=origin,
        origin_node=origin,
        title_fa="کار فنی",
        issue=ISSUE_024 if item_id.startswith("AR-ISS-024") else None,
        priority="P1" if item_id.startswith("AR-ISS-024") else "P3",
    )
    base.update(changes)
    return TransferItem(**base)  # type: ignore[arg-type]


def hw_item(origin: str = "N-HW-REP", **changes: object) -> TransferItem:
    base: dict[str, object] = dict(
        title_en="Hardware",
        title_fa="سخت‌افزار",
        lead="Saeed Akbari",
        lead_fa="سعید اکبری",
        collaborators=("Farzaneh Javadi",),
        collaborators_fa=("فرزانه جوادی",),
        documents=("AR-HW-012", "AR-HW-013"),
        gaps=("AR-HW-013",),
        risk=9,
        owner_node="N-HW-REP",
        role=ItemRole.OWNER if origin == "N-HW-REP" else ItemRole.SUPPORT,
    )
    base.update(changes)
    return item("AR-ISS-024/HW", origin, **base)


def win_item(**changes: object) -> TransferItem:
    base: dict[str, object] = dict(
        title_en="Windows client",
        title_fa="کلاینت ویندوز",
        status="blocked",
        lead="Roozbeh Mohseni",
        lead_fa="روزبه محسنی",
        depends_on=("AR-ISS-024/HW",),
        documents=("AR-SW-019",),
        gaps=("AR-HW-015",),
        risk=9,
    )
    base.update(changes)
    return item("AR-ISS-024/WIN", "N-SW-WIN", **base)


def closed_item(origin: str = "N-HW-REP") -> TransferItem:
    return item(
        "AR-ISS-034",
        origin,
        title_en="Workstation startup faults",
        title_fa="خطای راه‌اندازی ایستگاه",
        status="closed",
        lead="Saeed Akbari",
        lead_fa="سعید اکبری",
    )


def mobile_item(origin: str = "N-SW-MOB") -> TransferItem:
    return item(
        "AR-ISS-031",
        origin,
        title_en="Mobile app login failures",
        title_fa="خطای ورود اپلیکیشن موبایل",
        status="triaged",
        issue=ISSUE_031,
        lead="Nima Rad",
        lead_fa="نیما راد",
        risk=5,
    )


def team_hw(*items: TransferItem) -> NodeKnowledge:
    return NodeKnowledge(
        node_id="N-HW-REP",
        layer=3,
        name_en="Repair team",
        name_fa="تیم تعمیرات",
        documents=(DocumentRef("AR-HW-012", "1.2"),),
        items=items or (hw_item(), closed_item()),
        executors=(
            ExecutorRef("EX-HW-01", "Saeed Akbari", "سعید اکبری", 14),
            ExecutorRef("EX-HW-02", "Farzaneh Javadi", "فرزانه جوادی", None),
        ),
    )


def team_win() -> NodeKnowledge:
    return NodeKnowledge(
        node_id="N-SW-WIN",
        layer=3,
        name_en="Windows team",
        name_fa="تیم ویندوز",
        documents=(DocumentRef("AR-SW-019", "1.1"),),
        items=(win_item(),),
        executors=(ExecutorRef("EX-SW-01", "Roozbeh Mohseni", "روزبه محسنی", 10),),
    )


def team_mob() -> NodeKnowledge:
    return NodeKnowledge(
        node_id="N-SW-MOB",
        layer=3,
        name_en="Mobile team",
        name_fa="تیم موبایل",
        items=(mobile_item(),),
        executors=(ExecutorRef("EX-SW-02", "Nima Rad", "نیما راد", 6),),
    )


def empty_team(node_id: str = "N-HW-SAL") -> NodeKnowledge:
    return NodeKnowledge(
        node_id=node_id,
        layer=3,
        name_en="Sales team",
        name_fa="تیم فروش",
        executors=(ExecutorRef("EX-HW-09", "Ali Nouri", "علی نوری", None),),
    )


def deputy(node_id: str = "N-HW", name: str = "Hardware deputy") -> NodeKnowledge:
    return NodeKnowledge(
        node_id=node_id,
        layer=2,
        name_en=name,
        name_fa="معاونت",
        executors=(ExecutorRef(f"EX-{node_id}", "Deputy Head", "رئیس معاونت", 4),),
    )


def ceo() -> NodeKnowledge:
    return NodeKnowledge(
        node_id="N-CEO", layer=1, name_en="Chief executive", name_fa="مدیرعامل"
    )


def knowledge_map(*nodes: NodeKnowledge) -> dict[str, NodeKnowledge]:
    return {n.node_id: n for n in nodes}


def step(
    source: str, target: str, source_layer: int, target_layer: int, order: int = 1
) -> ProcessingStep:
    return ProcessingStep(
        order, source, target, source_layer, target_layer, source_layer
    )


def rule_reviewer() -> tuple[PackageReviewer, CaseJudgeAdapter]:
    validator = CitedFactValidator()
    adapter = CaseJudgeAdapter(RuleBasedJudge(default_rubric(), validator))
    return PackageReviewer(validator, adapter), adapter


def draft_for(
    sender: NodeKnowledge,
    target: str,
    layer: int,
    received: list | tuple = (),
    expected_children: int = 0,
) -> PackageDraft:
    return TransferPackageBuilder(VERSIONS).build(
        CYCLE,
        sender,
        target,
        RuleBook().for_layer(layer),
        received,
        expected_children=expected_children,
    )


def built(
    sender: NodeKnowledge, target: str, layer: int, received: list | tuple = ()
) -> BuiltPackage:
    reviewer, _ = rule_reviewer()
    return reviewer.review(
        draft_for(sender, target, layer, received, expected_children=len(received))
    )


@dataclass
class FakeChildPackage:
    """Minimal stand-in for an accepted child package (items, capacity, omitted, source node)."""

    source_node: str
    items: tuple
    capacity: object
    omitted: tuple = ()
