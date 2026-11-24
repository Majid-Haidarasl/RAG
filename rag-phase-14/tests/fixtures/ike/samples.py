"""Phase 9 IKE test helpers: a small synthetic issue with three sub-issues."""

from __future__ import annotations

from rag_core.ike.domain.comparison import KnowledgeHit, KnowledgeSearchResult
from rag_core.ike.domain.views import IssueView, ReferralView, SubItemView

NAMES = {
    "EX-SAEED-AKBARI": ("Saeed Akbari", "سعید اکبری"),
    "EX-ROOZBEH-MOHSENI": ("Roozbeh Mohseni", "روزبه محسنی"),
    "EX-YASAMAN-KARAMI": ("Yasaman Karami", "یاسمن کرمی"),
}


def sample_issue() -> IssueView:
    hw = SubItemView(
        "AR-ISS-050/HW",
        "HW",
        "Hardware: RAID controller",
        "N-HW-REP",
        "in_progress",
        title_fa="سخت‌افزار",
        related_documents=("AR-HW-012", "AR-HW-015"),
    )
    win = SubItemView(
        "AR-ISS-050/WIN",
        "WIN",
        "Windows client",
        "N-SW-WIN",
        "blocked",
        related_documents=("AR-SW-019", "AR-HW-015"),
        depends_on=("HW",),
    )
    web = SubItemView(
        "AR-ISS-050/WEB",
        "WEB",
        "Web reporting",
        "N-SW-WEB",
        "in_progress",
        supporting_nodes=("N-SW-UX",),
        related_documents=("AR-SW-017", "AR-RFP-025"),
        reserved_decision=True,
    )
    return IssueView(
        "AR-ISS-050",
        "Sample delivery delay",
        "N-LIB",
        "in_progress",
        40,
        title_fa="تأخیر نمونه",
        related_documents=("AR-ISS-050", "AR-HW-012", "AR-SW-017"),
        sub_items=(hw, win, web),
    )


def sample_referrals() -> dict[str, list[ReferralView]]:
    return {
        "AR-ISS-050/HW": [
            ReferralView(
                "AR-ISS-050/HW",
                "EX-SAEED-AKBARI",
                "Saeed Akbari",
                "lead",
                0.9,
                ("AR-HW-012", "AR-HW-015"),
            )
        ],
        "AR-ISS-050/WIN": [
            ReferralView(
                "AR-ISS-050/WIN",
                "EX-ROOZBEH-MOHSENI",
                "Roozbeh Mohseni",
                "lead",
                0.9,
                ("AR-SW-019", "AR-SW-016"),
            )
        ],
        "AR-ISS-050/WEB": [
            ReferralView(
                "AR-ISS-050/WEB",
                "EX-YASAMAN-KARAMI",
                "Yasaman Karami",
                "collaborator",
                0.54,
                ("AR-SW-020",),
            )
        ],
    }


def search_result(
    node: str,
    docs: list[str],
    visible: set[str],
    *,
    lexical: float = 5.0,
    vector: float | None = None,
    owners: tuple[str, ...] = (),
) -> KnowledgeSearchResult:
    hits = tuple(
        KnowledgeHit(d, i + 1, f"{d}@1.0/en#c{i:04d}", "en", lexical, vector)
        for i, d in enumerate(docs)
    )
    return KnowledgeSearchResult(
        "q",
        node,
        hits,
        frozenset(visible),
        owners,
        "hybrid" if vector is not None else "lexical",
    )


class FakeSearch:
    """``KnowledgeSearchPort`` returning a scripted result per node."""

    def __init__(self, results: dict[str, KnowledgeSearchResult]) -> None:
        self.results = results
        self.calls: list[tuple[str, str, int]] = []

    def search(self, query: str, node: str, top_k: int) -> KnowledgeSearchResult:
        self.calls.append((query, node, top_k))
        return self.results.get(node) or KnowledgeSearchResult(query, node)
