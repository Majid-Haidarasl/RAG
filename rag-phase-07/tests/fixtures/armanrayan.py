"""Small synthetic fixtures derived from ArmanRayan facts. No corpus files are read."""

from rag_core.hierarchy.domain.model import Layer, Node, NodeType, Organization
from rag_core.shared_kernel.identifiers import NodeIdentifier
from rag_core.shared_kernel.layer import LayerIndex


def arm_layers() -> list[Layer]:
    return [
        Layer(LayerIndex(0), "L0", "Strategic governance", "راهبری استراتژیک", default_detail_level="executive"),
        Layer(LayerIndex(1), "L1", "Parent organization", "سازمان مادر", default_detail_level="managerial"),
        Layer(LayerIndex(2), "L2", "Specialist deputies", "معاونت‌های تخصصی", default_detail_level="technical_summary"),
        Layer(LayerIndex(3), "L3", "Execution teams", "تیم‌ها و واحدهای اجرا", default_detail_level="detailed_technical"),
        Layer(LayerIndex(4), "L4", "Knowledge repository", "مخزن دانش داخلی", default_detail_level="detailed_technical"),
    ]


def seed_organization(*nodes: Node) -> Organization:
    org = Organization()
    for layer in arm_layers():
        org.register_layer(layer)
    for node in nodes:
        org.register_node(node)
    return org


def board() -> Node:
    return Node(
        NodeIdentifier("N-BRD"),
        "ArmanRayan Board of Directors",
        "هیئت‌مدیره آرمان‌رایان",
        NodeType.BOARD,
        LayerIndex(0),
        None,
    )


def ceo() -> Node:
    return Node(
        NodeIdentifier("N-CEO"),
        "Chief Executive Management",
        "مدیریت عامل",
        NodeType.PARENT_ORGANIZATION,
        LayerIndex(1),
        NodeIdentifier("N-BRD"),
    )


def software_deputy() -> Node:
    return Node(
        NodeIdentifier("N-SW"),
        "Software and Digital Products Deputy",
        "معاونت نرم‌افزار و محصولات دیجیتال",
        NodeType.DEPUTY,
        LayerIndex(2),
        NodeIdentifier("N-CEO"),
    )


def web_team() -> Node:
    return Node(
        NodeIdentifier("N-SW-WEB"),
        "Web-development Team",
        "تیم توسعه وب",
        NodeType.TEAM,
        LayerIndex(3),
        NodeIdentifier("N-SW"),
        is_leaf=True,
        capabilities=("django", "laravel", "node.js", "react"),
    )


def library() -> Node:
    return Node(
        NodeIdentifier("N-LIB"),
        "Organizational Knowledge Library",
        "کتابخانه دانش سازمانی آرمان‌رایان",
        NodeType.KNOWLEDGE_REPOSITORY,
        LayerIndex(4),
        NodeIdentifier("N-CEO"),
        is_leaf=True,
    )
