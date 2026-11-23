"""Load the judge calibration set (``data/judge/calibration-set.json``) and parser cases."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rag_core.judging.domain.cases import Expectation, JudgeCase, SourceBlock
from rag_core.judging.domain.rubric import OutputKind
from rag_core.shared_kernel.errors import InvariantError


def _source(data: dict[str, Any]) -> SourceBlock:
    order = data.get("order")
    return SourceBlock(
        label=str(data["label"]),
        text=str(data["text"]),
        document_id=str(data.get("document_id", "")),
        order=int(order) if order is not None else None,
        language=data.get("language"),
    )


def _expectation(data: dict[str, Any] | None) -> Expectation:
    data = data or {}
    return Expectation(
        status=str(data.get("status", "answered")),
        facts=tuple(tuple(str(a) for a in group) for group in data.get("facts") or ()),
        escalation=str(data.get("escalation", "")),
        items=tuple(str(i) for i in data.get("items") or ()),
        item_leads=tuple((str(i), tuple(str(n) for n in names)) for i, names in data.get("item_leads") or ()),
        gaps=tuple(str(g) for g in data.get("gaps") or ()),
    )


def case_from_dict(data: dict[str, Any], origin: str = "calibration") -> JudgeCase:
    return JudgeCase(
        case_id=str(data["id"]),
        kind=OutputKind(data["kind"]),
        language=str(data["language"]),
        task=str(data.get("task", "")),
        output=str(data.get("output", "")),
        sources=tuple(_source(s) for s in data.get("sources") or ()),
        expectation=_expectation(data.get("expected")),
        status=str(data.get("status", "answered")),
        escalation=str(data.get("escalation", "")),
        node=str(data.get("node", "")),
        origin=origin,
        gold=str(data.get("gold", "")),
        tags=tuple(str(t) for t in data.get("tags") or ()),
    )


def load_calibration(path: Path) -> list[JudgeCase]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = [case_from_dict(c) for c in data.get("cases") or []]
    ids = [c.case_id for c in cases]
    if len(ids) != len(set(ids)):
        raise InvariantError("duplicate calibration case ids")
    if any(not c.gold for c in cases):
        raise InvariantError("every calibration case needs a gold label")
    return cases


def load_parser_cases(path: Path) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = list(data.get("cases") or [])
    for c in cases:
        if "id" not in c or "raw" not in c or "expect" not in c:
            raise InvariantError("parser case needs id, raw and expect")
    return cases
