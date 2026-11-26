"""Transfer ACL over the real registry, issues and executors (no corpus read)."""

from pathlib import Path
from typing import ClassVar

import pytest

from rag_core.executors.application.services import load_executor_registry
from rag_core.executors.infrastructure.hierarchy_acl import HierarchyTeamDirectory
from rag_core.hierarchy.application.workflows import load_and_validate
from rag_core.issues.application.services import load_issue_registry
from rag_core.issues.infrastructure.hierarchy_acl import HierarchyOrgDirectory
from rag_core.processing.domain.plan import build_plan
from rag_core.processing.infrastructure.hierarchy_acl import tree_nodes
from rag_core.transfer.domain.levels import RuleBook
from rag_core.transfer.infrastructure.ike_acl import leads_and_lacks
from rag_core.transfer.infrastructure.sources_acl import (
    build_knowledge,
    document_versions,
    issue_context,
    items_for_node,
    layer_rules_from_registry,
    sender_level_mismatches,
    with_item_status,
)
from tests.fixtures.rag.fakes import rec

pytestmark = [pytest.mark.transfer, pytest.mark.transfer_pkg]

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def world():
    loaded = load_and_validate(ROOT / "data" / "registry")
    org = loaded.organization
    assert org is not None and loaded.ownership is not None
    issues = load_issue_registry(
        ROOT / "data" / "issues", HierarchyOrgDirectory(org)
    ).issues
    executors = load_executor_registry(
        ROOT / "data" / "executors", HierarchyTeamDirectory(org)
    ).executors
    return org, loaded.ownership, issues, executors


def _issue(issues, issue_id):
    return next(i for i in issues if str(i.identifier) == issue_id)


def test_issue_context_of_024(world) -> None:
    ctx = issue_context(_issue(world[2], "AR-ISS-024"))
    assert (
        ctx.issue_id,
        ctx.priority,
        ctx.progress,
        ctx.decision_amount_mtoman,
        ctx.risk,
    ) == ("AR-ISS-024", "P2", 62, 95, 8)
    assert ctx.due_on == "2024-10-11"
    assert ctx.title_fa


def test_items_of_repair_team(world) -> None:
    items = items_for_node("N-HW-REP", world[2])
    assert [i.item_id for i in items] == ["AR-ISS-024/HW", "AR-ISS-034"]
    hw = items[0]
    assert hw.role.value == "owner" and hw.documents == (
        "AR-HW-012",
        "AR-HW-013",
        "AR-HW-015",
    )
    assert hw.issue is not None and hw.issue.issue_id == "AR-ISS-024"


def test_supporting_and_legal_items(world) -> None:
    adv = items_for_node("N-HW-ADV", world[2])
    assert [(i.item_id, i.role.value, i.owner_node) for i in adv] == [
        ("AR-ISS-024/HW", "support", "N-HW-REP")
    ]
    lacks = {"AR-ISS-024/LEG": ("AR-FIN-010",)}
    leads = {
        "AR-ISS-024/LEG": (
            "Mahsa Jalali",
            "مهسا جلالی",
            ("Reza Abbasi",),
            ("رضا عباسی",),
        )
    }
    leg = items_for_node("N-ADM-LEG", world[2], leads, lacks)[0]
    assert (leg.status, leg.reserved_decision, leg.depends_on) == (
        "blocked",
        True,
        ("AR-ISS-024/HW",),
    )
    assert (leg.lead, leg.gaps, leg.collaborators) == (
        "Mahsa Jalali",
        ("AR-FIN-010",),
        ("Reza Abbasi",),
    )


def test_build_knowledge_counts(world) -> None:
    org, ownership, issues, executors = world
    knowledge = build_knowledge(org, ownership, issues, executors, {"AR-HW-012": "1.0"})
    assert len(knowledge) == 21
    assert sum(1 for k in knowledge.values() if k.items) == 11
    assert sum(len(k.items) for k in knowledge.values()) == 14
    assert sum(len(k.executors) for k in knowledge.values()) == 15
    assert [str(d) for d in knowledge["N-HW-REP"].documents] == ["AR-HW-012@1.0"]
    assert next(e.name_en for e in knowledge["N-SW-WEB"].executors) == "Hanieh Saadati"


def test_registry_levels_match_the_rules(world) -> None:
    org = world[0]
    book = RuleBook()
    assert book.registry_mismatches(layer_rules_from_registry(org)) == []
    plan = build_plan(tree_nodes(org))
    levels = {r.receiving_layer: r.level.value for r in book.rules}
    assert sender_level_mismatches(org, plan.senders, levels) == []
    assert sender_level_mismatches(org, ["N-HW"], {1: "executive"}) == [
        "N-HW: registry managerial != executive"
    ]


def test_update_copy_and_versions(world) -> None:
    org, ownership, issues, executors = world
    knowledge = build_knowledge(org, ownership, issues, executors, {})
    changed = with_item_status(knowledge, "N-HW-REP", "AR-ISS-024/HW", "resolved")
    assert changed["N-HW-REP"].items[0].status == "resolved"
    assert knowledge["N-HW-REP"].items[0].status == "in_progress"
    versions = document_versions(
        [
            rec("AR-HW-012", 1, "a", version="1.0"),
            rec("AR-HW-012", 2, "b", version="1.10"),
            rec("AR-HW-013", 1, "c", version="2.0"),
        ]
    )
    assert versions == {"AR-HW-012": "1.10", "AR-HW-013": "2.0"}


def test_ike_digest_to_leads_and_lacks() -> None:
    class Item:
        def __init__(self, item_id, lead, collaborators, lacks):
            self.item_id, self.lead, self.collaborators, self.lacks = (
                item_id,
                lead,
                collaborators,
                lacks,
            )

    class Digest:
        items: ClassVar[list] = [
            Item(
                "AR-ISS-024/HW",
                "EX-SAEED-AKBARI",
                ("EX-FARZANEH-JAVADI",),
                (("AR-HW-013", 0.4),),
            ),
            Item("AR-ISS-024/WIN", "", (), ()),
        ]

    names = {
        "EX-SAEED-AKBARI": ("Saeed Akbari", "سعید اکبری"),
        "EX-FARZANEH-JAVADI": ("Farzaneh Javadi", ""),
    }
    leads, lacks = leads_and_lacks(Digest(), names)  # type: ignore[arg-type]
    assert leads["AR-ISS-024/HW"] == (
        "Saeed Akbari",
        "سعید اکبری",
        ("Farzaneh Javadi",),
        ("Farzaneh Javadi",),
    )
    assert leads["AR-ISS-024/WIN"] == ("", "", (), ())
    assert lacks == {"AR-ISS-024/HW": ("AR-HW-013",)}
