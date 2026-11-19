"""Deterministic package text: fact lines, English text and Persian text.

``facts`` are the only source the texts (and an AI suggestion) may use.
Every identifier and number printed in ``english`` or ``persian`` is copied
from a fact line, so the shared-kernel ``FactValidator`` finds all of them.
The texts contain no tables (``|``) and no Markdown fences, and every item line
starts with the item id followed by its lead, so the rule judge can link a
lead to its sub-issue (Phase 10).
"""

from __future__ import annotations

from dataclasses import dataclass

from rag_core.transfer.domain.items import CapacitySummary, IssueGroup, TransferItem
from rag_core.transfer.domain.levels import AggregationMode, DetailLevelRule

STATUS_FA = {
    "open": "باز", "triaged": "بررسی‌شده", "in_progress": "در جریان", "blocked": "مسدود",
    "resolved": "حل‌شده", "closed": "بسته", "reopened": "بازگشایی‌شده",
}
LEVEL_FA = {
    "executive": "اجرایی-راهبردی", "managerial": "مدیریتی",
    "technical_summary": "خلاصهٔ فنی", "detailed_technical": "فنی تفصیلی",
}
NONE = "none"


@dataclass(frozen=True)
class RenderInput:
    cycle_id: str
    source_node: str
    source_name_en: str
    source_name_fa: str
    target_node: str
    target_layer: int
    rule: DetailLevelRule
    groups: tuple[IssueGroup, ...]
    omitted: tuple[str, ...]
    capacity: CapacitySummary
    citations: tuple[str, ...]
    received: int = 0
    expected_children: int = 0

    @property
    def items(self) -> list[TransferItem]:
        return [i for g in self.groups for i in g.items]

    @property
    def gap_pairs(self) -> list[tuple[str, str]]:
        return [(i.item_id, g) for i in self.items for g in i.gaps]

    @property
    def counts(self) -> dict[str, int]:
        items = self.items
        return {
            "groups": len(self.groups),
            "items": len(items),
            "open": sum(1 for i in items if i.is_open),
            "blocked": sum(1 for i in items if i.is_blocked),
            "reserved": sum(1 for i in items if i.reserved_decision and i.is_open),
            "gaps": len(self.gap_pairs),
            "omitted": len(self.omitted),
            "documents": len(self.citations),
        }


@dataclass(frozen=True)
class RenderedPackage:
    facts: tuple[str, ...]
    english: str
    persian: str
    fields: dict[str, str]
    expected_items: tuple[str, ...]
    expected_leads: tuple[tuple[str, tuple[str, ...]], ...]
    expected_gaps: tuple[str, ...]

    def words(self, language: str) -> int:
        return len((self.persian if language == "fa" else self.english).split())


def _join(values: tuple[str, ...] | list[str], sep: str = ", ", empty: str = NONE) -> str:
    values = [v for v in values if v]
    return sep.join(values) if values else empty


def _fa_status(status: str) -> str:
    return STATUS_FA.get(status, status)


# ----------------------------------------------------------------------------- facts
def _issue_fact(g: IssueGroup) -> str:
    c = g.issue
    parts = [f"issue {c.issue_id}: {c.title_en}", f"title_fa {c.title_fa or NONE}", f"status {c.status or NONE}",
             f"priority {c.priority or NONE}"]
    parts.append(f"progress {c.progress}%" if c.progress is not None else "progress unknown")
    parts.append(f"contract {c.contract_ref or NONE}")
    if c.decision_amount_mtoman is not None:
        parts.append(f"decision amount {c.decision_amount_mtoman} million toman")
    else:
        parts.append("decision amount none")
    parts.append(f"due {c.due_on or NONE}")
    parts.append(f"customer {c.customer or NONE}")
    return " | ".join(parts)


def _group_fact(g: IssueGroup) -> str:
    return (f"issue {g.group_id} items: {_join(list(g.item_ids))} | items {len(g.items)} | open {g.open_count} | "
            f"blocked {g.blocked_count} | reserved decision {_join(list(g.reserved_items))} | "
            f"owner nodes {_join(list(g.owner_nodes))}")


def _item_fact(i: TransferItem) -> str:
    return " | ".join([
        f"item {i.item_id}: {i.title_en}",
        f"title_fa {i.title_fa or NONE}",
        f"owner {i.owner_node}",
        f"role {i.role.value}",
        f"status {i.status}",
        f"priority {i.effective_priority or NONE}",
        f"part of {i.parent_id}",
        f"lead {i.lead or NONE}",
        f"lead_fa {i.lead_fa or NONE}",
        f"collaborators {_join(list(i.collaborators))}",
        f"collaborators_fa {_join(list(i.collaborators_fa))}",
        f"depends on {_join(list(i.depends_on))}",
        f"documents {_join(list(i.documents))}",
        f"knowledge lack {_join(list(i.gaps))}",
        f"acceptance {i.acceptance_output or NONE}",
        f"reserved decision {'yes' if i.reserved_decision else 'no'}",
    ])


def _capacity_fact(c: CapacitySummary) -> list[str]:
    lines = [f"capacity: executors {c.executors} | published {c.published} | hours per week {c.hours_per_week} | "
             f"unit planning {len(c.unit_planning)}: {_join(list(c.unit_planning))}"]
    for p in c.people:
        hours = f"{p.hours_per_week} h/week" if p.hours_per_week is not None else "unit planning"
        lines.append(f"executor {p.name_en} ({p.name_fa or NONE}): {hours}")
    return lines


def facts_for(inp: RenderInput) -> list[str]:
    n = inp.counts
    lines = [
        f"package {inp.cycle_id}: from {inp.source_node} to {inp.target_node} | receiving layer L{inp.target_layer} | "
        f"detail level {inp.rule.level.value}",
        f"sender {inp.source_node}: {inp.source_name_en} | name_fa {inp.source_name_fa or NONE}",
        f"counts: issues {n['groups']} | items {n['items']} | open {n['open']} | blocked {n['blocked']} | "
        f"reserved decisions {n['reserved']} | knowledge gaps {n['gaps']} | omitted {n['omitted']} | "
        f"documents {n['documents']} | received packages {inp.received} of {inp.expected_children}",
    ]
    contexts_done: set[str] = set()
    for g in inp.groups:
        if g.group_id not in contexts_done:
            contexts_done.add(g.group_id)
            lines.append(_issue_fact(g))
        if inp.rule.aggregation is AggregationMode.BY_ISSUE:
            lines.append(_group_fact(g))
        for item in g.items:
            lines.append(_item_fact(item))
    if inp.gap_pairs:
        lines.append("knowledge gaps: " + ", ".join(f"{a} -> {b}" for a, b in inp.gap_pairs))
    lines.extend(_capacity_fact(inp.capacity))
    lines.append(f"documents: {_join(list(inp.citations))}")
    lines.append(f"omitted: {_join(list(inp.omitted))}")
    return lines


# ----------------------------------------------------------------------------- shared pieces
def _issue_bits_en(g: IssueGroup) -> list[str]:
    c = g.issue
    bits = [f"status {c.status}"] if c.status else []
    if c.priority:
        bits.append(f"priority {c.priority}")
    if c.progress is not None:
        bits.append(f"progress {c.progress}%")
    if c.due_on:
        bits.append(f"due {c.due_on}")
    if c.decision_amount_mtoman is not None:
        bits.append(f"decision amount {c.decision_amount_mtoman} million toman")
    return bits


def _issue_bits_fa(g: IssueGroup) -> list[str]:
    c = g.issue
    bits = [f"وضعیت {_fa_status(c.status)}"] if c.status else []
    if c.priority:
        bits.append(f"اولویت {c.priority}")
    if c.progress is not None:
        bits.append(f"پیشرفت {c.progress}٪")
    if c.due_on:
        bits.append(f"موعد {c.due_on}")
    if c.decision_amount_mtoman is not None:
        bits.append(f"مبلغ تصمیم {c.decision_amount_mtoman} میلیون تومان")
    return bits


def _item_line_en(i: TransferItem, rule: DetailLevelRule, *, with_title: bool) -> str:
    bits: list[str] = []
    if rule.show_people:
        bits.append(f"lead {i.lead or NONE}")
    bits.append(i.status)
    if with_title:
        bits.append(i.title_en)
    bits.append(f"owner {i.owner_node}" + (" (support role)" if i.role.value == "support" else ""))
    if rule.show_collaborators and i.collaborators:
        bits.append(f"collaborators {_join(list(i.collaborators))}")
    if rule.show_dependencies and i.depends_on:
        bits.append(f"depends on {_join(list(i.depends_on))}")
    if rule.show_documents and i.documents and rule.max_documents_per_item:
        bits.append(f"documents {_join(list(i.documents[: rule.max_documents_per_item]))}")
    if rule.show_gaps == "per_item" and i.gaps:
        bits.append(f"knowledge gaps {_join(list(i.gaps))}")
    if i.reserved_decision and i.is_open:
        bits.append("reserved decision")
    return f"- {i.item_id}: " + "; ".join(bits) + "."


def _item_line_fa(i: TransferItem, rule: DetailLevelRule, *, with_title: bool) -> str:
    bits: list[str] = []
    if rule.show_people:
        bits.append(f"مجری اصلی {i.lead_fa or i.lead or '-'}")
    bits.append(_fa_status(i.status))
    if with_title:
        bits.append(i.title_fa or i.title_en)
    bits.append(f"مالک {i.owner_node}" + (" (نقش پشتیبان)" if i.role.value == "support" else ""))
    if rule.show_collaborators and i.collaborators:
        names = i.collaborators_fa if len(i.collaborators_fa) == len(i.collaborators) else i.collaborators
        bits.append(f"همکاران {_join(list(names), '، ')}")
    if rule.show_dependencies and i.depends_on:
        bits.append(f"وابسته به {_join(list(i.depends_on), '، ')}")
    if rule.show_documents and i.documents and rule.max_documents_per_item:
        bits.append(f"اسناد {_join(list(i.documents[: rule.max_documents_per_item]), '، ')}")
    if rule.show_gaps == "per_item" and i.gaps:
        bits.append(f"کمبود دانش {_join(list(i.gaps), '، ')}")
    if i.reserved_decision and i.is_open:
        bits.append("تصمیم رزروشده")
    return f"- {i.item_id}: " + "؛ ".join(bits) + "."


def _capacity_en(c: CapacitySummary, mode: str) -> str:
    if mode == "per_person":
        if not c.people:
            return "Capacity: no executor is registered at this node."
        people = []
        for p in c.people:
            people.append(f"{p.name_en} {p.hours_per_week} h/week" if p.hours_per_week is not None
                          else f"{p.name_en} unit planning")
        return f"Capacity: {c.executors} executors ({', '.join(people)})."
    return (f"Capacity: {c.executors} executors, {c.published} with published hours ({c.hours_per_week} h/week), "
            f"{len(c.unit_planning)} by unit planning.")


def _capacity_fa(c: CapacitySummary, mode: str) -> str:
    if mode == "per_person":
        if not c.people:
            return "ظرفیت: مجری ثبت‌شده‌ای در این گره نیست."
        people = []
        for p in c.people:
            name = p.name_fa or p.name_en
            people.append(f"{name} {p.hours_per_week} ساعت در هفته" if p.hours_per_week is not None
                          else f"{name} با برنامه‌ریزی واحد")
        return f"ظرفیت: {c.executors} مجری ({'، '.join(people)})."
    return (f"ظرفیت: {c.executors} مجری، {c.published} نفر با ساعت اعلام‌شده ({c.hours_per_week} ساعت در هفته)، "
            f"{len(c.unit_planning)} نفر با برنامه‌ریزی واحد.")


def _tail_en(inp: RenderInput) -> list[str]:
    out = [f"Sources: {_join(list(inp.citations))}."]
    if inp.omitted:
        out.append(f"Omitted by the detail-level limit: {_join(list(inp.omitted))}.")
    if inp.expected_children:
        out.append(f"Received packages: {inp.received} of {inp.expected_children}.")
    return out


def _tail_fa(inp: RenderInput) -> list[str]:
    out = [f"منابع: {_join(list(inp.citations), '، ', '-')}."]
    if inp.omitted:
        out.append(f"به‌خاطر سقف این سطح جزئیات نیامده: {_join(list(inp.omitted), '، ')}.")
    if inp.expected_children:
        out.append(f"بسته‌های دریافتی: {inp.received} از {inp.expected_children}.")
    return out


# ----------------------------------------------------------------------------- texts
def english_text(inp: RenderInput) -> str:
    rule = inp.rule
    n = inp.counts
    level = rule.level.value
    title = "Board brief" if level == "executive" else "Transfer package"
    out = [f"{title} {inp.cycle_id} from {inp.source_node} to {inp.target_node} ({level})."]
    if level == "executive":
        out.append(f"Open issues {n['groups']}, blocked items {n['blocked']}, reserved decisions {n['reserved']}, "
                   f"knowledge gaps {n['gaps']}.")
        if inp.groups:
            out.append("Risks:")
            for g in inp.groups:
                bits = [g.issue.title_en, *_issue_bits_en(g), f"blocked {g.blocked_count} of {len(g.items)} items",
                        f"items {_join(list(g.item_ids))}"]
                out.append(f"- {g.group_id}: " + "; ".join(bits) + ".")
        else:
            out.append("Risks: no open issue was reported.")
        decisions = _decisions_en(inp.groups)
        out.append("Decisions requested: " + ("; ".join(decisions) if decisions else "none requested") + ".")
    else:
        out.append(f"Items {n['items']}, open {n['open']}, blocked {n['blocked']}, knowledge gaps {n['gaps']}.")
        if not inp.groups:
            out.append("No open or recent issue is held by this node.")
        for g in inp.groups:
            if rule.aggregation is AggregationMode.BY_ISSUE and g.is_parent:
                out.append(f"{g.group_id}: {g.issue.title_en}; " + "; ".join(_issue_bits_en(g)) + ".")
                out.extend(_item_line_en(i, rule, with_title=False) for i in g.items)
            else:
                out.extend(_item_line_en(i, rule, with_title=True) for i in g.items)
                if rule.aggregation is AggregationMode.ITEMS:
                    for i in g.items:
                        c = i.issue
                        if i.is_subissue and c is not None and c.progress is not None:
                            out.append(f"  {i.item_id} is part of {c.issue_id} (progress {c.progress}%).")
        if rule.show_gaps == "list" and inp.gap_pairs:
            out.append("Knowledge gaps: " + ", ".join(f"{a} -> {b}" for a, b in inp.gap_pairs) + ".")
        if rule.show_capacity != "none":
            out.append(_capacity_en(inp.capacity, rule.show_capacity))
    out.extend(_tail_en(inp))
    return "\n".join(out)


def persian_text(inp: RenderInput) -> str:
    rule = inp.rule
    n = inp.counts
    level = rule.level.value
    title = "گزارش هیئت‌مدیره" if level == "executive" else "بستهٔ انتقال دانش"
    out = [f"{title} {inp.cycle_id} از {inp.source_node} به {inp.target_node} (سطح {LEVEL_FA.get(level, level)})."]
    if level == "executive":
        out.append(f"مسئله‌های باز {n['groups']}، موارد مسدود {n['blocked']}، تصمیم‌های رزروشده {n['reserved']}، "
                   f"کمبودهای دانش {n['gaps']}.")
        if inp.groups:
            out.append("ریسک‌ها:")
            for g in inp.groups:
                bits = [g.issue.title_fa or g.issue.title_en, *_issue_bits_fa(g),
                        f"{g.blocked_count} مورد مسدود از {len(g.items)} مورد",
                        f"موارد {_join(list(g.item_ids), '، ')}"]
                out.append(f"- {g.group_id}: " + "؛ ".join(bits) + ".")
        else:
            out.append("ریسک‌ها: مسئلهٔ بازی گزارش نشده است.")
        decisions = _decisions_fa(inp.groups)
        out.append("تصمیم‌های درخواستی: " + ("؛ ".join(decisions) if decisions else "درخواستی نیست") + ".")
    else:
        out.append(f"موارد {n['items']}، باز {n['open']}، مسدود {n['blocked']}، کمبودهای دانش {n['gaps']}.")
        if not inp.groups:
            out.append("این گره مسئلهٔ باز یا تازه‌ای ندارد.")
        for g in inp.groups:
            if rule.aggregation is AggregationMode.BY_ISSUE and g.is_parent:
                out.append(f"{g.group_id}: {g.issue.title_fa or g.issue.title_en}؛ " + "؛ ".join(_issue_bits_fa(g)) + ".")
                out.extend(_item_line_fa(i, rule, with_title=False) for i in g.items)
            else:
                out.extend(_item_line_fa(i, rule, with_title=True) for i in g.items)
                if rule.aggregation is AggregationMode.ITEMS:
                    for i in g.items:
                        c = i.issue
                        if i.is_subissue and c is not None and c.progress is not None:
                            out.append(f"  {i.item_id} بخشی از {c.issue_id} است (پیشرفت {c.progress}٪).")
        if rule.show_gaps == "list" and inp.gap_pairs:
            out.append("کمبودهای دانش: " + "، ".join(f"{a} ← {b}" for a, b in inp.gap_pairs) + ".")
        if rule.show_capacity != "none":
            out.append(_capacity_fa(inp.capacity, rule.show_capacity))
    out.extend(_tail_fa(inp))
    return "\n".join(out)


def _decisions_en(groups: tuple[IssueGroup, ...]) -> list[str]:
    out: list[str] = []
    for g in groups:
        bits: list[str] = []
        if g.issue.decision_amount_mtoman is not None:
            bits.append(f"decision amount {g.issue.decision_amount_mtoman} million toman")
        if g.reserved_items:
            bits.append(f"reserved decision on {_join(list(g.reserved_items))}")
        if bits:
            out.append(f"{g.group_id}: " + ", ".join(bits))
    return out


def _decisions_fa(groups: tuple[IssueGroup, ...]) -> list[str]:
    out: list[str] = []
    for g in groups:
        bits: list[str] = []
        if g.issue.decision_amount_mtoman is not None:
            bits.append(f"مبلغ تصمیم {g.issue.decision_amount_mtoman} میلیون تومان")
        if g.reserved_items:
            bits.append(f"تصمیم رزروشده دربارهٔ {_join(list(g.reserved_items), '، ')}")
        if bits:
            out.append(f"{g.group_id}: " + "، ".join(bits))
    return out


# ----------------------------------------------------------------------------- fields
def fields_for(inp: RenderInput, english: str, persian: str) -> dict[str, str]:
    items = inp.items
    risks = [f"{i.item_id}: {i.status}" + (", reserved decision" if i.reserved_decision else "")
             for i in items if i.is_open and (i.is_blocked or i.reserved_decision or i.gaps)]
    decisions = _decisions_en(inp.groups)
    deps = [f"{i.item_id} -> {d}" for i in items for d in i.depends_on]
    gaps = [f"{a} -> {b}" for a, b in inp.gap_pairs]
    n = inp.counts
    return {
        "cycle": inp.cycle_id,
        "risks": "; ".join(risks) if risks else "no blocking risk recorded",
        "decisions_requested": "; ".join(decisions) if decisions else "none requested",
        "source_references": _join(list(inp.citations)),
        "key_issues": _join([i.item_id for i in items]),
        "summary": english,
        "summary_fa": persian,
        "dependencies": "; ".join(deps) if deps else NONE,
        "knowledge_gaps": "; ".join(gaps) if gaps else NONE,
        "capacity": _capacity_en(inp.capacity, "counts"),
        "omitted": _join(list(inp.omitted)),
        "counts": (f"issues {n['groups']}; items {n['items']}; open {n['open']}; blocked {n['blocked']}; "
                   f"reserved {n['reserved']}; gaps {n['gaps']}; omitted {n['omitted']}; "
                   f"received {inp.received} of {inp.expected_children}"),
    }


def render(inp: RenderInput) -> RenderedPackage:
    english = english_text(inp)
    persian = persian_text(inp)
    rule = inp.rule
    items = inp.items
    leads: tuple[tuple[str, tuple[str, ...]], ...] = ()
    if rule.show_people:
        leads = tuple((i.item_id, tuple(x for x in (i.lead, i.lead_fa) if x)) for i in items if i.lead)
    gaps: tuple[str, ...] = ()
    if rule.show_gaps in {"per_item", "list"}:
        gaps = tuple(sorted({g for i in items for g in i.gaps}))
    return RenderedPackage(
        facts=tuple(facts_for(inp)),
        english=english,
        persian=persian,
        fields=fields_for(inp, english, persian),
        expected_items=tuple(i.item_id for i in items),
        expected_leads=leads,
        expected_gaps=gaps,
    )
