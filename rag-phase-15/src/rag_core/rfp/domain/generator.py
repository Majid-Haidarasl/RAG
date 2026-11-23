"""Template-first RFP generation from Phase 12 key issues, gaps and a reviewed blueprint.

1. ``select_candidates`` decides which key issues need an outside supplier:
   an issue whose category is a sourcing category (``procurement``) or that is
   listed as a target (issue -> sub-issue), and that a blueprint serves.
   Other key issues are reported with the reason (``not_sourcing`` or
   ``no_blueprint``); nothing is invented for them.
2. ``build_rfp`` writes fact lines and the RFP text from the same values:
   the RFP identity, the key issues it serves (rank, score, main factors), the
   sub-issue, the knowledge gaps on it, every requirement by section, the
   weighted evaluation criteria and the knowledge links. The text is the fact
   lines under section headings, so every number and id in it is in the facts.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from rag_core.prioritization.domain.brief import LABELS_EN, LABELS_FA, SEVERITY_FA, STATUS_FA, num
from rag_core.rfp.domain.blueprint import SECTION_ORDER, Blueprint

DEFAULT_HEADINGS: dict[str, tuple[str, str]] = {
    "identity": ("Request for proposal", "درخواست پیشنهاد"),
    "context": ("Why this RFP (key issues of the cycle)", "چرا این درخواست (مسئله‌های کلیدی چرخه)"),
    "gaps": ("Knowledge gaps to cover", "شکاف‌های دانشی که باید پوشش داده شود"),
    "need": ("Need", "نیاز"),
    "scope": ("Scope", "دامنه"),
    "deliverables": ("Deliverables", "خروجی‌ها"),
    "exclusions": ("Exclusions", "موارد خارج از دامنه"),
    "architecture": ("Architecture", "معماری"),
    "security": ("Security", "امنیت"),
    "testing": ("Testing", "آزمون"),
    "response_format": ("Response format", "قالب پاسخ"),
    "evaluation": ("Evaluation", "ارزیابی"),
    "acceptance": ("Acceptance", "پذیرش"),
    "knowledge": ("Knowledge handover", "تحویل دانش"),
    "criteria": ("Evaluation criteria and weights", "معیارها و وزن‌های ارزیابی"),
    "links": ("Knowledge links (where the result is recorded)", "پیوند به دانش گره‌ها (محل ثبت نتیجه)"),
}
MAX_GAPS = 6


@dataclass(frozen=True)
class KeyIssueView:
    issue_id: str
    title_en: str
    title_fa: str
    category: str
    status: str
    rank: int
    score: float
    top_factors: tuple[tuple[str, float], ...] = ()


@dataclass(frozen=True)
class ItemView:
    item_id: str
    status: str
    owner_node: str = ""
    title_en: str = ""
    title_fa: str = ""


@dataclass(frozen=True)
class GapView:
    gap_id: str
    subject: str
    severity: str
    title_en: str
    title_fa: str
    issue_id: str = ""


@dataclass(frozen=True)
class Candidate:
    issue_id: str
    reason: str                 # target | procurement | not_sourcing | no_blueprint
    blueprint_id: str = ""
    item_id: str = ""

    @property
    def has_rfp(self) -> bool:
        return bool(self.blueprint_id)

    def to_dict(self) -> dict[str, object]:
        return {"issue_id": self.issue_id, "reason": self.reason, "blueprint_id": self.blueprint_id,
                "item_id": self.item_id}


def select_candidates(key: Sequence[KeyIssueView], blueprints: Iterable[Blueprint],
                      categories: Iterable[str] = ("procurement",),
                      targets: Mapping[str, str] | None = None) -> list[Candidate]:
    bps = list(blueprints)
    cats = set(categories)
    targets = dict(targets or {})
    out: list[Candidate] = []
    for k in sorted(key, key=lambda v: (v.rank, v.issue_id)):
        sourcing = k.issue_id in targets or k.category in cats
        if not sourcing:
            out.append(Candidate(k.issue_id, "not_sourcing"))
            continue
        bp = next((b for b in bps if k.issue_id in b.issues), None)
        if bp is None:
            out.append(Candidate(k.issue_id, "no_blueprint"))
            continue
        item = targets.get(k.issue_id) or (bp.item if bp.item.startswith(k.issue_id + "/") else "")
        out.append(Candidate(k.issue_id, "target" if k.issue_id in targets else "procurement", bp.blueprint_id,
                             item))
    return out


@dataclass(frozen=True)
class RfpDraft:
    rfp_id: str
    blueprint_id: str
    language: str
    facts: tuple[str, ...]
    text: str
    items: tuple[str, ...]          # ids the RFP text must name (RFP, item, issues)
    gaps: tuple[str, ...]           # mandatory requirement ids and gap subjects it should name
    sections: tuple[str, ...]
    requirement_ids: tuple[str, ...]
    issues: tuple[str, ...]
    gap_ids: tuple[str, ...] = ()
    lines: dict[str, list[str]] = field(default_factory=dict)

    @property
    def words(self) -> int:
        return len(self.text.split())

    @property
    def chars(self) -> int:
        return len(self.text)

    def to_dict(self) -> dict[str, object]:
        return {"rfp_id": self.rfp_id, "blueprint_id": self.blueprint_id, "language": self.language,
                "facts": list(self.facts), "text": self.text, "items": list(self.items), "gaps": list(self.gaps),
                "sections": list(self.sections), "requirements": list(self.requirement_ids),
                "issues": list(self.issues), "gap_ids": list(self.gap_ids), "words": self.words,
                "chars": self.chars}


def _factors(factors: Iterable[tuple[str, float]], fa: bool) -> str:
    labels = LABELS_FA if fa else LABELS_EN
    sep = "، " if fa else ", "
    return sep.join(f"{labels.get(k, k)} {num(v)}" for k, v in factors)


def relevant_gaps(gaps: Iterable[GapView], issues: Iterable[str], item: str) -> list[GapView]:
    """Gaps on the RFP's sub-issue or on the issues themselves (not on sibling sub-issues)."""
    ids = set(issues)
    out = [g for g in gaps if (item and g.subject == item) or g.subject in ids]
    return out[:MAX_GAPS]


def build_rfp(bp: Blueprint, candidates: Sequence[Candidate], key: Mapping[str, KeyIssueView],
              gaps: Iterable[GapView], language: str, cycle_id: str, item: ItemView | None = None,
              headings: Mapping[str, tuple[str, str]] | None = None) -> RfpDraft:
    fa = language == "fa"
    heads = {**DEFAULT_HEADINGS, **dict(headings or {})}

    def head(name: str) -> str:
        en, fa_text = heads.get(name, (name, name))
        return (fa_text if fa else en) + ":"

    served = [c for c in candidates if c.blueprint_id == bp.blueprint_id]
    issues = tuple(c.issue_id for c in served)
    item_id = item.item_id if item else bp.item
    facts: list[str] = []
    text: list[str] = []
    lines: dict[str, list[str]] = {}

    def add(section: str, row: str) -> None:
        facts.append(row)
        if section not in lines:
            lines[section] = []
            text.append(head(section))
        lines[section].append(row)
        text.append(row)

    title = bp.title(language)
    if fa:
        add("identity", f"درخواست پیشنهاد {bp.rfp_id}: {title}. گره مالک {bp.owner_node}؛ چرخه {cycle_id}.")
    else:
        add("identity", f"RFP {bp.rfp_id}: {title}. Owner {bp.owner_node}; cycle {cycle_id}.")
    for c in served:
        k = key.get(c.issue_id)
        if k is None:
            continue
        k_title = k.title_fa if fa and k.title_fa else k.title_en
        factors = _factors(k.top_factors, fa)
        if fa:
            reason = "هدف تعیین‌شده" if c.reason == "target" else "تأمین از بیرون"
            add("context", f"{k.issue_id} مسئله کلیدی {k.rank} چرخه {cycle_id} است: {k_title}؛ امتیاز {num(k.score)} "
                           f"از 100؛ عوامل اصلی: {factors}؛ دلیل درخواست: {reason}.")
        else:
            reason = "configured target" if c.reason == "target" else "procurement"
            add("context", f"{k.issue_id} is key issue {k.rank} of cycle {cycle_id}: {k_title}; score {num(k.score)} "
                           f"of 100; main factors: {factors}; reason for the RFP: {reason}.")
    if item is not None:
        i_title = item.title_fa if fa and item.title_fa else item.title_en
        if fa:
            add("context", f"زیرمسئله {item.item_id} ({STATUS_FA.get(item.status, item.status)})، گره مالک "
                           f"{item.owner_node}: {i_title}.")
        else:
            add("context", f"Sub-issue {item.item_id} ({item.status}), owner {item.owner_node}: {i_title}.")
    gap_list = relevant_gaps(gaps, issues, item_id)
    for g in gap_list:
        if fa:
            add("gaps", f"شکاف {g.gap_id} (شدت {SEVERITY_FA.get(g.severity, g.severity)}): {g.title_fa}.")
        else:
            add("gaps", f"Gap {g.gap_id} ({g.severity}): {g.title_en}.")
    mandatory = "الزامی" if fa else "mandatory"
    optional = "توصیه‌شده" if fa else "recommended"
    for section in SECTION_ORDER:
        for r in (r for r in bp.requirements if r.section.value == section):
            add(section, f"[{r.requirement_id}] ({mandatory if r.mandatory else optional}) {r.statement(language)}")
    for c in bp.criteria:
        if fa:
            add("criteria", f"معیار {c.criterion_id} ({c.name('fa')}): وزن {c.percent}٪؛ موارد سنجش: {c.considers('fa')}.")
        else:
            add("criteria", f"Criterion {c.criterion_id} ({c.name('en')}): weight {c.percent}%; considers "
                            f"{c.considers('en')}.")
    for link in bp.links:
        who = f" ({link.executor})" if link.executor else ""
        add("links", f"{link.link_id}: {link.node}{who} — {link.role(language)}.")
    items = tuple(dict.fromkeys([bp.rfp_id, *([item_id] if item_id else []), *issues]))
    expected = tuple(dict.fromkeys([*bp.mandatory_ids(), *(g.subject for g in gap_list)]))
    return RfpDraft(bp.rfp_id, bp.blueprint_id, language, tuple(facts), "\n".join(text), items, expected,
                    bp.sections(), tuple(r.requirement_id for r in bp.requirements), issues,
                    tuple(g.gap_id for g in gap_list), lines)
