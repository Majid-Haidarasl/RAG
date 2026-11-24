"""``config/eval.yaml`` -> ``EvalSettings`` (unknown keys are errors, lists become tuples)."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml

from rag_core.shared_kernel.errors import InvariantError
from rag_core.tuning.domain.required_ids import IdVariant
from rag_core.tuning.domain.variants import KINDS, Selection, SelectionRule

JUDGE_VARIANTS = ("baseline", "strict")


@dataclass(frozen=True)
class EvalFiles:
    dataset: str = "eval/datasets/armanrayan-qa.jsonl"
    results_dir: str = "eval/results"
    calibration: str = "data/judge/calibration-set.json"
    phase13_results: str = "results/phase-13"
    qa_prompt_dir: str = "config/prompts/qa"
    strict_judge_dir: str = "config/prompts/judge_strict"
    ids_prompt_dir: str = "config/prompts/rfp_ids"


@dataclass(frozen=True)
class RetrievalVariant:
    id: str
    description: str = ""
    top_k: int = 5
    candidate_k: int = 30
    lexical_weight: float = 1.0
    vector_weight: float = 1.0
    budget_tokens: int = 3500

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise InvariantError("a retrieval variant needs an id")
        if not 1 <= self.top_k <= self.candidate_k:
            raise InvariantError(
                f"retrieval variant {self.id}: need 1 <= top_k <= candidate_k"
            )
        if (
            self.lexical_weight < 0
            or self.vector_weight < 0
            or self.lexical_weight + self.vector_weight <= 0
        ):
            raise InvariantError(
                f"retrieval variant {self.id}: weights must be >= 0 and not both 0"
            )
        if self.budget_tokens < 500:
            raise InvariantError(
                f"retrieval variant {self.id}: budget_tokens must be >= 500"
            )


@dataclass(frozen=True)
class EvalLive:
    enabled: bool = True
    generation_models: tuple[str, ...] = ("qwen3:8b",)
    qa: bool = True
    judge: bool = True
    ids: bool = True
    max_generations: int = 120
    max_judge_calls: int = 100

    def __post_init__(self) -> None:
        if self.max_generations < 0 or self.max_judge_calls < 0:
            raise InvariantError("live caps must be >= 0")


@dataclass(frozen=True)
class EvalSettings:
    config_version: str = "0.14.0"
    files: EvalFiles = field(default_factory=EvalFiles)
    retrieval_variants: tuple[RetrievalVariant, ...] = (RetrievalVariant("baseline"),)
    qa_prompts: tuple[str, ...] = ("qa.answer",)
    judge_prompts: tuple[str, ...] = JUDGE_VARIANTS
    id_variants: tuple[str, ...] = tuple(v.value for v in IdVariant)
    selection_rules: dict[str, SelectionRule] = field(default_factory=dict)
    selection: dict[str, Selection] = field(default_factory=dict)
    live: EvalLive = field(default_factory=EvalLive)

    def variant(self, variant_id: str) -> RetrievalVariant:
        for v in self.retrieval_variants:
            if v.id == variant_id:
                return v
        raise InvariantError(f"unknown retrieval variant {variant_id}")

    def chosen(self, kind: str) -> str:
        sel = self.selection.get(kind)
        if sel is None:
            raise InvariantError(f"no selection for {kind}")
        return sel.variant

    def known_variants(self) -> dict[str, tuple[str, ...]]:
        return {
            "retrieval": tuple(v.id for v in self.retrieval_variants),
            "qa_prompt": self.qa_prompts,
            "judge_prompt": self.judge_prompts,
            "ai_ids": self.id_variants,
            "generation_model": self.live.generation_models,
        }


def _mapping(data: Any, where: str) -> dict[str, Any]:
    data = data or {}
    if not isinstance(data, dict):
        raise InvariantError(f"eval config {where} must be a mapping")
    return data


def _build(cls: type, data: Any, where: str) -> Any:
    data = _mapping(data, where)
    known = {f.name for f in fields(cls)}
    unknown = sorted(set(data) - known)
    if unknown:
        raise InvariantError(
            f"unknown keys in eval config {where}: {', '.join(unknown)}"
        )
    return cls(**{k: tuple(v) if isinstance(v, list) else v for k, v in data.items()})


def _rule(kind: str, data: Any) -> SelectionRule:
    data = _mapping(data, f"selection_rules.{kind}")
    unknown = sorted(
        set(data) - {"primary", "higher_is_better", "tie_breakers", "min_gain"}
    )
    if unknown:
        raise InvariantError(
            f"unknown keys in eval config selection_rules.{kind}: {', '.join(unknown)}"
        )
    ties = []
    for t in data.get("tie_breakers") or []:
        if not isinstance(t, list) or len(t) != 2:
            raise InvariantError(
                f"selection_rules.{kind}: a tie breaker is [metric, higher_is_better]"
            )
        ties.append((str(t[0]), bool(t[1])))
    return SelectionRule(
        str(data.get("primary", "")),
        bool(data.get("higher_is_better", True)),
        tuple(ties),
        float(data.get("min_gain", 0.0)),
    )


def _selection(kind: str, data: Any) -> Selection:
    data = _mapping(data, f"selection.{kind}")
    unknown = sorted(set(data) - {"variant", "reason"})
    if unknown:
        raise InvariantError(
            f"unknown keys in eval config selection.{kind}: {', '.join(unknown)}"
        )
    return Selection(
        kind,
        str(data.get("variant", "")),
        " ".join(str(data.get("reason", "")).split()),
    )


TOP_KEYS = {
    "config_version",
    "files",
    "retrieval_variants",
    "qa_prompts",
    "judge_prompts",
    "id_variants",
    "selection_rules",
    "selection",
    "live",
}


def eval_settings_from_dict(data: dict[str, Any]) -> EvalSettings:
    data = _mapping(data, "root")
    unknown = sorted(set(data) - TOP_KEYS)
    if unknown:
        raise InvariantError(f"unknown eval config sections: {', '.join(unknown)}")
    variants = tuple(
        _build(RetrievalVariant, v, "retrieval_variants[]")
        for v in data.get("retrieval_variants") or []
    )
    if not variants:
        raise InvariantError("eval config needs at least one retrieval variant")
    ids = [v.id for v in variants]
    if len(ids) != len(set(ids)) or ids[0] != "baseline":
        raise InvariantError(
            "retrieval variant ids must be unique and the first one must be 'baseline'"
        )
    judge_prompts = tuple(str(j) for j in data.get("judge_prompts") or JUDGE_VARIANTS)
    if set(judge_prompts) - set(JUDGE_VARIANTS):
        raise InvariantError(f"judge_prompts must be among {', '.join(JUDGE_VARIANTS)}")
    id_variants = tuple(
        str(v) for v in data.get("id_variants") or [v.value for v in IdVariant]
    )
    known_ids = {v.value for v in IdVariant}
    if set(id_variants) - known_ids:
        raise InvariantError(
            f"id_variants must be among {', '.join(sorted(known_ids))}"
        )
    qa_prompts = tuple(str(p) for p in data.get("qa_prompts") or ["qa.answer"])
    rules = {
        str(k): _rule(str(k), v)
        for k, v in _mapping(data.get("selection_rules"), "selection_rules").items()
    }
    unknown_rules = sorted(set(rules) - set(KINDS))
    if unknown_rules:
        raise InvariantError(
            f"unknown selection rule kinds: {', '.join(unknown_rules)}"
        )
    selection = {
        str(k): _selection(str(k), v)
        for k, v in _mapping(data.get("selection"), "selection").items()
    }
    return EvalSettings(
        config_version=str(data.get("config_version", "0.14.0")),
        files=_build(EvalFiles, data.get("files"), "files"),
        retrieval_variants=variants,
        qa_prompts=qa_prompts,
        judge_prompts=judge_prompts,
        id_variants=id_variants,
        selection_rules=rules,
        selection=selection,
        live=_build(EvalLive, data.get("live"), "live"),
    )


def load_eval_settings(path: Path) -> EvalSettings:
    with Path(path).open(encoding="utf-8") as fh:
        return eval_settings_from_dict(yaml.safe_load(fh) or {})
