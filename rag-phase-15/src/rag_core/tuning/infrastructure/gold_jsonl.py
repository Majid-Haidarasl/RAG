"""``eval/datasets/armanrayan-qa.jsonl`` <-> ``GoldItem`` (one JSON object per line, UTF-8)."""

from __future__ import annotations

from collections.abc import Iterable
import json
from pathlib import Path
from typing import Any

from rag_core.shared_kernel.errors import InvariantError
from rag_core.tuning.domain.gold import Evidence, GoldItem

REQUIRED = ("id", "pair", "language", "node", "question", "expected_status")
OPTIONAL = (
    "expected_docs",
    "expected_outside_docs",
    "expected_escalation",
    "expected_facts",
    "evidence",
    "reference_answer",
    "partial_answer",
    "detail",
    "origin",
)
EVIDENCE_KEYS = {"document_id", "language", "quote"}


def _strings(value: Any, where: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise InvariantError(f"{where} must be a list of strings")
    return tuple(value)


def item_from_dict(data: dict[str, Any], where: str = "item") -> GoldItem:
    if not isinstance(data, dict):
        raise InvariantError(f"{where}: must be a JSON object")
    unknown = sorted(set(data) - set(REQUIRED) - set(OPTIONAL))
    if unknown:
        raise InvariantError(f"{where}: unknown keys {', '.join(unknown)}")
    missing = [k for k in REQUIRED if not str(data.get(k, "")).strip()]
    if missing:
        raise InvariantError(f"{where}: missing {', '.join(missing)}")
    facts = data.get("expected_facts") or []
    if not isinstance(facts, list):
        raise InvariantError(f"{where}: expected_facts must be a list of lists")
    groups = tuple(_strings(g, f"{where}: expected_facts group") for g in facts)
    if any(not g for g in groups):
        raise InvariantError(f"{where}: an expected_facts group is empty")
    evidence = []
    for e in data.get("evidence") or []:
        if not isinstance(e, dict) or set(e) != EVIDENCE_KEYS:
            raise InvariantError(
                f"{where}: evidence needs exactly {', '.join(sorted(EVIDENCE_KEYS))}"
            )
        evidence.append(
            Evidence(str(e["document_id"]), str(e["language"]), str(e["quote"]))
        )
    return GoldItem(
        id=str(data["id"]),
        pair=str(data["pair"]),
        language=str(data["language"]),
        node=str(data["node"]),
        question=str(data["question"]),
        expected_status=str(data["expected_status"]),
        expected_docs=_strings(data.get("expected_docs"), f"{where}: expected_docs"),
        expected_outside_docs=_strings(
            data.get("expected_outside_docs"), f"{where}: expected_outside_docs"
        ),
        expected_escalation=str(data.get("expected_escalation") or ""),
        expected_facts=groups,
        evidence=tuple(evidence),
        reference_answer=str(data.get("reference_answer") or ""),
        partial_answer=str(data.get("partial_answer") or ""),
        detail=str(data.get("detail") or "short"),
        origin=str(data.get("origin") or ""),
    )


def item_to_dict(item: GoldItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "pair": item.pair,
        "language": item.language,
        "node": item.node,
        "question": item.question,
        "expected_status": item.expected_status,
        "expected_docs": list(item.expected_docs),
        "expected_outside_docs": list(item.expected_outside_docs),
        "expected_escalation": item.expected_escalation,
        "expected_facts": [list(g) for g in item.expected_facts],
        "evidence": [
            {"document_id": e.document_id, "language": e.language, "quote": e.quote}
            for e in item.evidence
        ],
        "reference_answer": item.reference_answer,
        "partial_answer": item.partial_answer,
        "detail": item.detail,
        "origin": item.origin,
    }


def parse_gold(text: str, name: str = "dataset") -> list[GoldItem]:
    items: list[GoldItem] = []
    for no, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise InvariantError(
                f"{name} line {no}: invalid JSON ({exc.msg})"
            ) from None
        items.append(item_from_dict(data, f"{name} line {no}"))
    if not items:
        raise InvariantError(f"{name}: no items")
    return items


def load_gold(path: Path) -> list[GoldItem]:
    path = Path(path)
    return parse_gold(path.read_text(encoding="utf-8"), path.name)


def dump_gold(items: Iterable[GoldItem]) -> str:
    return "".join(
        json.dumps(item_to_dict(i), ensure_ascii=False) + "\n" for i in items
    )
