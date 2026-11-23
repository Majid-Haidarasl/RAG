"""Load ``config/prompts/judge/*.yaml``: the rubric and the judge prompts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from rag_core.judging.domain.prompts import (
    DEFAULT_RETRY_NOTE,
    DEFAULT_SCOPE_NOTES,
    LANGUAGE_NAMES,
    JudgePromptSet,
)
from rag_core.judging.domain.rubric import Criterion, OutputKind, Rubric
from rag_core.shared_kernel.errors import InvariantError

KINDS = tuple(k.value for k in OutputKind)


def _read(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict) or "id" not in data:
        raise InvariantError(f"{Path(path).name}: missing id")
    return data


def rubric_from_dict(data: dict[str, Any]) -> Rubric:
    criteria = []
    for item in data.get("criteria") or []:
        guidance = item.get("guidance") or {}
        unknown = sorted(set(guidance) - set(KINDS))
        if unknown:
            raise InvariantError(f"criterion {item.get('key')}: unknown output kinds {', '.join(unknown)}")
        criteria.append(Criterion(
            key=str(item["key"]),
            max_points=int(item["max"]),
            min_points=int(item["min"]),
            title_en=str(item.get("title_en", "")),
            title_fa=str(item.get("title_fa", "")),
            aliases=tuple(str(a) for a in item.get("aliases") or ()),
            guidance=tuple((k, " ".join(str(v).split())) for k, v in guidance.items()),
        ))
    return Rubric(str(data["id"]), str(data["version"]), tuple(criteria), out_of=int(data.get("out_of", 20)),
                  accept_total=int(data.get("accept_total", 18)))


def load_rubric(path: Path) -> Rubric:
    return rubric_from_dict(_read(path))


def prompt_from_dict(data: dict[str, Any]) -> JudgePromptSet:
    kinds = tuple(str(k) for k in data.get("kinds") or ())
    unknown = sorted(set(kinds) - set(KINDS))
    if unknown:
        raise InvariantError(f"{data.get('id')}: unknown output kinds {', '.join(unknown)}")
    notes = dict(DEFAULT_SCOPE_NOTES)
    notes.update({str(k): " ".join(str(v).split()) for k, v in (data.get("scope_notes") or {}).items()})
    return JudgePromptSet(
        prompt_id=str(data["id"]),
        version=str(data["version"]),
        kinds=kinds,
        system=str(data["system"]),
        user=str(data["user"]),
        retry_note=" ".join(str(data.get("retry_note", "")).split()) or DEFAULT_RETRY_NOTE,
        scope_notes=notes,
        language_names=dict(data.get("language_names") or LANGUAGE_NAMES),
    )


def load_judge_prompts(directory: Path) -> dict[str, JudgePromptSet]:
    """Map output kind → prompt set. Every kind must be covered exactly once."""
    by_kind: dict[str, JudgePromptSet] = {}
    for path in sorted(Path(directory).glob("*.yaml")):
        data = _read(path)
        if data.get("type") != "prompt":
            continue
        prompt = prompt_from_dict(data)
        for kind in prompt.kinds:
            if kind in by_kind:
                raise InvariantError(f"output kind {kind} has two prompts: {by_kind[kind].prompt_id}, {prompt.prompt_id}")
            by_kind[kind] = prompt
    missing = [k for k in KINDS if k not in by_kind]
    if missing:
        raise InvariantError(f"no judge prompt for: {', '.join(missing)}")
    return by_kind
