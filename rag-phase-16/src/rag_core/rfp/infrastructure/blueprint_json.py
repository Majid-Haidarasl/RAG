"""``data/rfp/rfp-blueprints.json`` -> ``Blueprint`` objects (unknown keys are rejected)."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from rag_core.rfp.domain.blueprint import RESPONSE_SECTIONS, Blueprint, Criterion, KnowledgeLink, Requirement
from rag_core.shared_kernel.errors import InvariantError

FILE_NAME = "rfp-blueprints.json"
TOP_KEYS = {"schema_version", "note", "blueprints"}
BP_KEYS = {"id", "rfp_id", "title_en", "title_fa", "owner_node", "issues", "item", "reference_document",
           "response_sections", "requirements", "criteria", "links"}
REQ_KEYS = {"id", "section", "mandatory", "answered_in", "statement_en", "statement_fa", "evidence"}
CRT_KEYS = {"id", "name_en", "name_fa", "weight", "considers_en", "considers_fa", "evidence"}
LNK_KEYS = {"id", "node", "executor", "requirements", "role_en", "role_fa", "evidence"}


def _check(rec: Any, allowed: set[str], where: str) -> dict:
    if not isinstance(rec, dict):
        raise InvariantError(f"{where} must be an object")
    unknown = sorted(set(rec) - allowed)
    if unknown:
        raise InvariantError(f"{where}: unknown keys {', '.join(unknown)}")
    return rec


def requirement_from(rec: dict) -> Requirement:
    rec = _check(rec, REQ_KEYS, f"requirement {rec.get('id', '?') if isinstance(rec, dict) else '?'}")
    return Requirement(str(rec.get("id", "")), rec.get("section", ""), str(rec.get("statement_en", "")),
                       str(rec.get("statement_fa", "")), bool(rec.get("mandatory", True)),
                       str(rec.get("answered_in", "") or ""), tuple(rec.get("evidence") or ()))


def criterion_from(rec: dict) -> Criterion:
    rec = _check(rec, CRT_KEYS, f"criterion {rec.get('id', '?') if isinstance(rec, dict) else '?'}")
    return Criterion(str(rec.get("id", "")), str(rec.get("name_en", "")), str(rec.get("name_fa", "")),
                     Decimal(str(rec.get("weight", "0"))), str(rec.get("considers_en", "")),
                     str(rec.get("considers_fa", "")), tuple(rec.get("evidence") or ()))


def link_from(rec: dict) -> KnowledgeLink:
    rec = _check(rec, LNK_KEYS, f"link {rec.get('id', '?') if isinstance(rec, dict) else '?'}")
    return KnowledgeLink(str(rec.get("id", "")), str(rec.get("node", "")), str(rec.get("role_en", "")),
                         str(rec.get("role_fa", "")), str(rec.get("executor", "") or ""),
                         tuple(rec.get("requirements") or ()), tuple(rec.get("evidence") or ()))


def blueprint_from(rec: dict) -> Blueprint:
    rec = _check(rec, BP_KEYS, f"blueprint {rec.get('id', '?') if isinstance(rec, dict) else '?'}")
    return Blueprint(
        blueprint_id=str(rec.get("id", "")), rfp_id=str(rec.get("rfp_id", "")),
        title_en=str(rec.get("title_en", "")), title_fa=str(rec.get("title_fa", "")),
        owner_node=str(rec.get("owner_node", "")), issues=tuple(rec.get("issues") or ()),
        requirements=tuple(requirement_from(r) for r in rec.get("requirements") or ()),
        criteria=tuple(criterion_from(c) for c in rec.get("criteria") or ()),
        item=str(rec.get("item", "") or ""), reference_document=str(rec.get("reference_document", "") or ""),
        response_sections=tuple(rec.get("response_sections") or RESPONSE_SECTIONS),
        links=tuple(link_from(link) for link in rec.get("links") or ()),
    )


def blueprints_from_dict(data: dict) -> list[Blueprint]:
    data = _check(data, TOP_KEYS, "blueprint file")
    if int(data.get("schema_version", 1)) != 1:
        raise InvariantError("unsupported blueprint schema_version")
    return [blueprint_from(b) for b in data.get("blueprints") or ()]


def read_blueprint_dict(folder: Path) -> dict:
    return json.loads((Path(folder) / FILE_NAME).read_text(encoding="utf-8"))


def load_blueprints(folder: Path) -> list[Blueprint]:
    return blueprints_from_dict(read_blueprint_dict(folder))
