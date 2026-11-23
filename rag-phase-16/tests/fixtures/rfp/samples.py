"""Phase 13 test helpers: the shipped blueprint and proposal registry, Phase 12-like views, texts."""

from __future__ import annotations

import copy
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

from rag_core.proposals.domain.model import ProposalRegistry
from rag_core.proposals.infrastructure.registry_json import read_registry_dict, registry_from_dict
from rag_core.rfp.domain.blueprint import Blueprint
from rag_core.rfp.domain.generator import GapView, ItemView, KeyIssueView
from rag_core.rfp.infrastructure.blueprint_json import blueprints_from_dict, read_blueprint_dict

REPO = Path(__file__).resolve().parents[3]
BLUEPRINT_DIR = REPO / "data" / "rfp"
PROPOSAL_DIR = REPO / "data" / "proposals"
PROMPT_DIR = REPO / "config" / "prompts" / "rfp"
CONFIG = REPO / "config" / "rfp.yaml"

NODES = {"N-SW", "N-SW-WEB", "N-SW-UX", "N-SW-SUP", "N-ADM-LEG", "N-ADM-FIN", "N-LIB", "N-CEO"}
DOCS = {"AR-RFP-025", "AR-SW-016", "AR-SW-022", "AR-LEG-009", "AR-FIN-010", "AR-TRN-026"}
ISSUES = {"AR-ISS-024", "AR-ISS-024/WEB", "AR-ISS-024/HW", "AR-ISS-031", "AR-ISS-035"}
EXECUTORS = {"EX-NAZANIN-FARAHANI": "N-SW-WEB", "EX-HANIEH-SAADATI": "N-SW-WEB", "EX-YASAMAN-KARAMI": "N-SW-UX",
             "EX-NILOUFAR-AHMADI": "N-SW-SUP", "EX-REZA-ABBASI": "N-ADM-FIN", "EX-MAHSA-JALALI": "N-ADM-LEG"}
MANDATORY = ("REQ-NEED", "REQ-SCOPE", "REQ-DELIVERABLES", "REQ-EXCLUSIONS", "REQ-RESPONSE", "REQ-EVALUATION",
             "REQ-ACCEPTANCE")
CYCLE = "1403-Q2"


@lru_cache(maxsize=1)
def _raw_blueprints() -> dict:
    return read_blueprint_dict(BLUEPRINT_DIR)


def raw_blueprints() -> dict:
    return copy.deepcopy(_raw_blueprints())


def shipped_blueprint() -> Blueprint:
    return blueprints_from_dict(raw_blueprints())[0]


@lru_cache(maxsize=1)
def _raw_registry() -> dict:
    return read_registry_dict(PROPOSAL_DIR)


def raw_registry() -> dict:
    return copy.deepcopy(_raw_registry())


def shipped_registry() -> ProposalRegistry:
    return registry_from_dict(raw_registry())


# ---- blueprint edits (frozen dataclasses -> replace) -------------------------------------
def with_requirement(bp: Blueprint, requirement_id: str, **changes: object) -> Blueprint:
    reqs = tuple(replace(r, **changes) if r.requirement_id == requirement_id else r for r in bp.requirements)
    return replace(bp, requirements=reqs)


def without_requirement(bp: Blueprint, requirement_id: str) -> Blueprint:
    return replace(bp, requirements=tuple(r for r in bp.requirements if r.requirement_id != requirement_id))


def with_link(bp: Blueprint, link_id: str, **changes: object) -> Blueprint:
    return replace(bp, links=tuple(replace(x, **changes) if x.link_id == link_id else x for x in bp.links))


def with_criterion(bp: Blueprint, criterion_id: str, **changes: object) -> Blueprint:
    return replace(bp, criteria=tuple(replace(c, **changes) if c.criterion_id == criterion_id else c
                                      for c in bp.criteria))


# ---- Phase 12-like inputs (values of the real 1403-Q2 run) --------------------------------
def key_views() -> list[KeyIssueView]:
    return [
        KeyIssueView("AR-ISS-024", "Azarpakhsh warehouse delivery delay", "تأخیر تحویل انبار آذرپخش",
                     "delivery_delay", "in_progress", 1, 82.75, (("urgency", 12.0), ("risk", 12.0), ("priority", 11.25))),
        KeyIssueView("AR-ISS-031", "Schedule slip", "لغزش زمان‌بندی", "schedule", "open", 2, 33.92,
                     (("urgency", 9.0),)),
        KeyIssueView("AR-ISS-035", "Azarpakhsh reporting contractor selection", "انتخاب پیمانکار گزارش‌گیری آذرپخش",
                     "procurement", "open", 3, 30.17, (("priority", 7.5), ("urgency", 7.5), ("risk", 6.0))),
    ]


def item_view() -> ItemView:
    return ItemView("AR-ISS-024/WEB", "in_progress", "N-SW-WEB", "Web reporting module", "ماژول گزارش‌گیری وب")


def gap_views() -> list[GapView]:
    return [
        GapView("KL:AR-ISS-024/WEB", "AR-ISS-024/WEB", "medium", "Knowledge lack on the web reporting module",
                "کمبود دانش در ماژول گزارش‌گیری وب", "AR-ISS-024"),
        GapView("KL:AR-ISS-024/HW", "AR-ISS-024/HW", "high", "Knowledge lack on the hardware part",
                "کمبود دانش در بخش سخت‌افزار", "AR-ISS-024"),
        GapView("UI:AR-ISS-035", "AR-ISS-035", "low", "The contractor selection has no recorded decision yet",
                "انتخاب پیمانکار هنوز تصمیم ثبت‌شده ندارد", "AR-ISS-035"),
    ]


TARGETS = {"AR-ISS-024": "AR-ISS-024/WEB"}


# ---- synthetic corpus text ----------------------------------------------------------------
def blueprint_texts(bp: Blueprint) -> dict[tuple[str, str], list[str]]:
    """Text of AR-RFP-025 / AR-SW-016 made of the blueprint's own statements (so they ground)."""
    out: dict[tuple[str, str], list[str]] = {}
    for lang in ("fa", "en"):
        chunks = [r.statement(lang) for r in bp.requirements] + [x.role(lang) for x in bp.links]
        chunks.append("وزن فنی 60 درصد و وزن مالی 40 درصد است." if lang == "fa"
                      else "The technical weight is 60 percent and the financial weight 40 percent.")
        out[("AR-RFP-025", lang)] = chunks
        out[("AR-SW-016", lang)] = ["Django is the default backend." if lang == "en" else "Django بک‌اند پیش‌فرض است."]
    return out


def registry_texts(registry: ProposalRegistry) -> dict[tuple[str, str], list[str]]:
    """Text of AR-RFP-025 with the evaluation sheet numbers and the recorded statements."""
    en = ["Proposal A costs 285 million toman over 7 weeks; technical 82, financial 74, weighted 78.8 in total.",
          "Proposal B costs 240 million toman over 5 weeks; technical 68, financial 86, weighted 75.2 in total."]
    fa = ["پیشنهاد الف ۲۸۵ میلیون تومان در ۷ هفته؛ فنی ۸۲، مالی ۷۴، وزنی ۷۸٫۸ در مجموع.",
          "پیشنهاد ب ۲۴۰ میلیون تومان در ۵ هفته؛ فنی ۶۸، مالی ۸۶، وزنی ۷۵٫۲ در مجموع."]
    for p in registry.proposals:
        en += [p.feedback_en, "; ".join(p.clarifications_en)]
        fa += [p.feedback_fa, "؛ ".join(p.clarifications_fa)]
    if registry.decision is not None:
        en.append(registry.decision.reason_en)
        fa.append(registry.decision.reason_fa)
    return {("AR-RFP-025", "en"): [t for t in en if t], ("AR-RFP-025", "fa"): [t for t in fa if t]}
