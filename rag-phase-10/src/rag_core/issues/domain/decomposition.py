"""Rule-based decomposition of an issue into sub-issues per cause path / unit.

Each ``CausePathRule`` describes one cause path of the ArmanRayan knowledge
corpus (AR-ORG-002 s.4–6, AR-EXE-023, AR-ISS-024 s.3): trigger phrases in
English and Persian, the owner node, supporting nodes, related standards,
dependencies on other paths and whether the path carries a reserved
(Board-level) decision.

Matching is deterministic: the issue text (title + description, both
languages) is normalized with the Phase 5 tokenizer; a phrase matches when
all of its tokens occur. A rule fires on ≥ ``min_hits`` distinct phrases.
Affected nodes not covered by any fired rule get one generic sub-issue each
("per affected unit" fallback). Owners must exist in the Phase 6 registry
(checked through the ``OrgDirectory`` port).

AR-ISS-024 explicitly warns against collapsing the paths into a vague
"server problem", so the generic word *server* is not a hardware trigger.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rag_core.issues.domain.model import Issue, IssueStatus, SubIssue
from rag_core.issues.domain.ports import OrgDirectory
from rag_core.knowledge.domain.fingerprint import tokens
from rag_core.shared_kernel.errors import NotFoundError
from rag_core.shared_kernel.identifiers import DocumentId, IssueId, NodeIdentifier


@dataclass(frozen=True)
class CausePathRule:
    code: str
    title_en: str
    title_fa: str
    owner_node: str
    phrases: tuple[str, ...]
    supporting_nodes: tuple[str, ...] = ()
    related_documents: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()
    reserved_decision: bool = False
    min_hits: int = 1
    scope: str = ""

    def phrase_tokens(self) -> list[tuple[str, frozenset[str]]]:
        return [(p, frozenset(tokens(p))) for p in self.phrases]

    def hits(self, text_tokens: frozenset[str]) -> list[str]:
        return [p for p, toks in self.phrase_tokens() if toks and toks <= text_tokens]


@dataclass(frozen=True)
class SubIssueDraft:
    code: str
    title: str
    title_fa: str
    owner_node: str
    supporting_nodes: tuple[str, ...]
    related_documents: tuple[str, ...]
    depends_on: tuple[str, ...]
    reserved_decision: bool
    matched: tuple[str, ...]
    scope: str = ""
    rule: str = ""

    def to_subissue(self, parent: IssueId, position: int) -> SubIssue:
        return SubIssue(
            identifier=IssueId(f"{parent}/{self.code}"),
            title=self.title,
            status=IssueStatus.OPEN,
            position=position,
            owner_node=NodeIdentifier(self.owner_node),
            supporting_nodes=tuple(NodeIdentifier(n) for n in self.supporting_nodes),
            related_documents=tuple(DocumentId(d) for d in self.related_documents),
            depends_on=self.depends_on,
            scope=self.scope,
            title_fa=self.title_fa,
            reserved_decision=self.reserved_decision,
        )


ARMANRAYAN_RULES: tuple[CausePathRule, ...] = (
    CausePathRule(
        code="HW",
        title_en="Hardware: RAID controller and server RAM compatibility",
        title_fa="سخت‌افزار: سازگاری کنترلر RAID و حافظه RAM سرور",
        owner_node="N-HW-REP",
        phrases=("raid", "controller", "ram", "memory", "firmware", "کنترلر", "حافظه", "رم", "فرمور"),
        supporting_nodes=("N-HW-ADV", "N-HW-ASM"),
        related_documents=("AR-HW-012", "AR-HW-013", "AR-HW-015"),
        scope="Controller, RAM and assembly compatibility; diagnosis, replacement advice and joint bench tests",
    ),
    CausePathRule(
        code="WIN",
        title_en="Windows client requirements and drivers",
        title_fa="نیازمندی‌های کلاینت ویندوزی و درایورها",
        owner_node="N-SW-WIN",
        phrases=("windows", "driver", "desktop", ".net", "ویندوز", "ویندوزی", "درایور", "کلاینت"),
        related_documents=("AR-SW-019", "AR-SW-016", "AR-HW-015"),
        depends_on=("HW",),
        scope="C#/.NET client, installation prerequisites and multi-station tests after component changes",
    ),
    CausePathRule(
        code="WEB",
        title_en="Web reporting delay",
        title_fa="تأخیر ماژول گزارش‌گیری وب",
        owner_node="N-SW-WEB",
        phrases=("web reporting", "web report", "reporting module", "dashboard", "گزارش وب", "گزارشگیری وب", "داشبورد"),
        supporting_nodes=("N-SW-UX",),
        related_documents=("AR-SW-017", "AR-RFP-025"),
        scope="Reporting API contract, dashboard compatibility and report-data acceptance",
    ),
    CausePathRule(
        code="LEG",
        title_en="Contract and delivery schedule",
        title_fa="قرارداد و زمان‌بندی تحویل",
        owner_node="N-ADM-LEG",
        phrases=("contract", "penalty", "amendment", "delivery date", "delivery schedule", "delivery delay",
                 "قرارداد", "جریمه", "الحاقیه", "تاریخ تحویل", "تأخیر تحویل"),
        supporting_nodes=("N-ADM-FIN",),
        related_documents=("AR-LEG-009", "AR-FIN-010"),
        depends_on=("HW",),
        reserved_decision=True,
        scope="Nonconformity versus scope, delay penalty, extension and amendment for approval",
    ),
    CausePathRule(
        code="FIN",
        title_en="Billing and receivables",
        title_fa="صورت‌وضعیت و مطالبات",
        owner_node="N-ADM-FIN",
        phrases=("receivable", "invoice", "billing", "مطالبه", "مطالبات", "صورتحساب"),
        related_documents=("AR-FIN-010", "AR-FIN-008"),
        scope="Billing, receivables and project cost-centre records",
    ),
    CausePathRule(
        code="MOB",
        title_en="Mobile application delivery",
        title_fa="تحویل اپلیکیشن موبایل",
        owner_node="N-SW-MOB",
        phrases=("mobile", "flutter", "موبایل", "فلاتر"),
        related_documents=("AR-SW-018",),
        scope="Flutter delivery and API consumption",
    ),
    CausePathRule(
        code="SUP",
        title_en="Support incident and SLA",
        title_fa="رخداد پشتیبانی و SLA",
        owner_node="N-SW-SUP",
        phrases=("outage", "incident", "sla", "قطعی", "رخداد"),
        related_documents=("AR-SW-022",),
        scope="Incident intake, priority under AR-SW-022 and escalation",
    ),
    CausePathRule(
        code="UX",
        title_en="User experience and interface acceptance",
        title_fa="پذیرش تجربه کاربری و رابط",
        owner_node="N-SW-UX",
        phrases=("wireframe", "usability", "user experience", "تجربه کاربری", "وایرفریم"),
        related_documents=("AR-SW-020",),
        scope="Readability and workflow acceptance",
    ),
)


@dataclass
class RuleBasedDecomposer:
    rules: tuple[CausePathRule, ...] = ARMANRAYAN_RULES
    directory: OrgDirectory | None = None
    per_unit_fallback: bool = True
    events: list[str] = field(default_factory=list)

    def decompose(self, issue: Issue) -> list[SubIssueDraft]:
        text_tokens = frozenset(tokens(issue.text))
        drafts: list[SubIssueDraft] = []
        for rule in self.rules:
            hits = rule.hits(text_tokens)
            if len(hits) >= rule.min_hits:
                drafts.append(
                    SubIssueDraft(
                        code=rule.code, title=rule.title_en, title_fa=rule.title_fa, owner_node=rule.owner_node,
                        supporting_nodes=rule.supporting_nodes, related_documents=rule.related_documents,
                        depends_on=rule.depends_on, reserved_decision=rule.reserved_decision,
                        matched=tuple(hits), scope=rule.scope, rule=rule.code,
                    )
                )
        fired = {d.code for d in drafts}
        drafts = [  # dependencies only on paths that actually exist in this issue
            SubIssueDraft(**{**d.__dict__, "depends_on": tuple(x for x in d.depends_on if x in fired)})
            for d in drafts
        ]
        if self.per_unit_fallback:
            covered = {d.owner_node for d in drafts} | {n for d in drafts for n in d.supporting_nodes}
            covered.add(str(issue.owning_node))
            for node in issue.affected_nodes:
                nid = str(node)
                if nid in covered:
                    continue
                code = "U" + nid.removeprefix("N-").replace("-", "")
                drafts.append(
                    SubIssueDraft(
                        code=code[:12], title=f"Contribution of {nid}", title_fa=f"سهم {nid}", owner_node=nid,
                        supporting_nodes=(), related_documents=(), depends_on=(), reserved_decision=False,
                        matched=(), scope="Per affected unit (no cause-path rule matched)", rule="per_unit",
                    )
                )
                covered.add(nid)
        if self.directory is not None:
            for d in drafts:
                for n in (d.owner_node, *d.supporting_nodes):
                    if not self.directory.exists(n):
                        raise NotFoundError(f"decomposition owner {n} for {d.code} is not in the registry")
        return drafts

    def apply(self, issue: Issue, drafts: list[SubIssueDraft] | None = None) -> list[SubIssue]:
        """Add drafts as sub-issues (idempotent: existing codes are skipped)."""
        drafts = self.decompose(issue) if drafts is None else drafts
        existing = {s.code for s in issue.subissues}
        position = max((s.position for s in issue.subissues), default=0)
        added: list[SubIssue] = []
        for d in drafts:
            if d.code in existing:
                continue
            position += 1
            sub = d.to_subissue(issue.identifier, position)
            issue.add_subissue(sub)
            added.append(sub)
        return added
