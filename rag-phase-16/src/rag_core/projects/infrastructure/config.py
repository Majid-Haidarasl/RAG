"""``config/projects.yaml`` -> ``ProjectSettings`` (unknown keys are rejected)."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml

from rag_core.prioritization.domain.model import Caps, Weights
from rag_core.research_gaps.domain.rules import (
    DEFAULT_SEVERITY,
    RULE_ORDER,
    RuleSetting,
)
from rag_core.shared_kernel.errors import InvariantError

DEFAULT_WEIGHTS = {
    "priority": 0.15,
    "severity": 0.10,
    "urgency": 0.15,
    "risk": 0.15,
    "dependents": 0.10,
    "exposure": 0.10,
    "blocked": 0.10,
    "gaps": 0.10,
    "spread": 0.05,
}


@dataclass(frozen=True)
class CycleSettings:
    id: str = "1403-Q2"
    cutoff: str = "1403-06-31"


@dataclass(frozen=True)
class StorageSettings:
    registry_dir: str = "data/projects"
    csv_dir: str = "exports/project-tracking"


@dataclass(frozen=True)
class PrioritySettings:
    weights: Weights = field(default_factory=lambda: Weights(DEFAULT_WEIGHTS))
    caps: Caps = field(default_factory=Caps)
    key_count: int = 3
    key_min_score: float = 25.0
    sensitivity_ratios: tuple[float, ...] = (0.8, 1.2)
    risk_threshold: int = 7

    def __post_init__(self) -> None:
        if self.key_count < 1:
            raise InvariantError("prioritization.key_count must be >= 1")
        if not self.sensitivity_ratios or any(r <= 0 for r in self.sensitivity_ratios):
            raise InvariantError(
                "prioritization.sensitivity_ratios must be positive numbers"
            )


@dataclass(frozen=True)
class ModelSettings:
    model: str = "qwen3:8b"
    think: bool = False
    format: str = "json"
    keep_alive: str = "30m"
    timeout_s: float = 180.0
    options: dict[str, Any] = field(
        default_factory=lambda: {
            "temperature": 0.2,
            "top_p": 0.9,
            "seed": 42,
            "num_ctx": 8192,
            "num_predict": 768,
        }
    )


@dataclass(frozen=True)
class LiveSettings:
    languages: tuple[str, ...] = ("fa", "en")
    llm_judge: bool = True

    def __post_init__(self) -> None:
        langs = tuple(self.languages)
        if not langs or any(lang not in {"fa", "en"} for lang in langs):
            raise InvariantError("live.languages must be a non-empty list of fa / en")
        object.__setattr__(self, "languages", langs)


@dataclass(frozen=True)
class ProjectSettings:
    config_version: str = "0.12.0"
    case: str = "AR-ISS-024"
    cycle: CycleSettings = field(default_factory=CycleSettings)
    storage: StorageSettings = field(default_factory=StorageSettings)
    gap_rules: dict[str, RuleSetting] = field(
        default_factory=lambda: {
            c: RuleSetting(True, DEFAULT_SEVERITY[c]) for c in RULE_ORDER
        }
    )
    prioritization: PrioritySettings = field(default_factory=PrioritySettings)
    model: ModelSettings = field(default_factory=ModelSettings)
    live: LiveSettings = field(default_factory=LiveSettings)


TOP_KEYS = frozenset(
    {
        "config_version",
        "case",
        "cycle",
        "storage",
        "gap_rules",
        "prioritization",
        "model",
        "live",
    }
)


def _plain(cls: type, data: Any, section: str) -> Any:
    data = data or {}
    if not isinstance(data, dict):
        raise InvariantError(f"projects config section {section!r} must be a mapping")
    known = {f.name for f in fields(cls)}
    unknown = sorted(set(data) - known)
    if unknown:
        raise InvariantError(
            f"unknown keys in projects config {section!r}: {', '.join(unknown)}"
        )
    if "id" in data:
        data = {**data, "id": str(data["id"])}
    if "cutoff" in data:
        data = {**data, "cutoff": str(data["cutoff"])}
    return cls(**data)


def _gap_rules(data: Any) -> dict[str, RuleSetting]:
    data = data or {}
    if not isinstance(data, dict):
        raise InvariantError("projects config section 'gap_rules' must be a mapping")
    unknown = sorted(set(data) - set(RULE_ORDER))
    if unknown:
        raise InvariantError(
            f"unknown gap rules in projects config: {', '.join(unknown)}"
        )
    out: dict[str, RuleSetting] = {}
    for code in RULE_ORDER:
        rec = data.get(code) or {}
        if not isinstance(rec, dict) or set(rec) - {"enabled", "severity"}:
            raise InvariantError(
                f"gap rule {code}: only 'enabled' and 'severity' are allowed"
            )
        try:
            out[code] = RuleSetting(
                bool(rec.get("enabled", True)),
                str(rec.get("severity", DEFAULT_SEVERITY[code])),
            )
        except ValueError as exc:
            raise InvariantError(f"gap rule {code}: {exc}") from None
    return out


def _priority(data: Any) -> PrioritySettings:
    data = dict(data or {})
    allowed = {
        "weights",
        "caps",
        "key_count",
        "key_min_score",
        "sensitivity_ratios",
        "risk_threshold",
    }
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise InvariantError(
            f"unknown keys in projects config 'prioritization': {', '.join(unknown)}"
        )
    caps = data.get("caps") or {}
    if set(caps) - {f.name for f in fields(Caps)}:
        raise InvariantError("unknown keys in prioritization.caps")
    return PrioritySettings(
        weights=Weights(data.get("weights") or DEFAULT_WEIGHTS),
        caps=Caps(**{k: int(v) for k, v in caps.items()}),
        key_count=int(data.get("key_count", 3)),
        key_min_score=float(data.get("key_min_score", 25.0)),
        sensitivity_ratios=tuple(
            float(r) for r in data.get("sensitivity_ratios", (0.8, 1.2))
        ),
        risk_threshold=int(data.get("risk_threshold", 7)),
    )


def project_settings_from_dict(data: dict[str, Any]) -> ProjectSettings:
    unknown = sorted(set(data) - TOP_KEYS)
    if unknown:
        raise InvariantError(f"unknown projects config sections: {', '.join(unknown)}")
    return ProjectSettings(
        config_version=str(data.get("config_version", "0.12.0")),
        case=str(data.get("case", "AR-ISS-024")),
        cycle=_plain(CycleSettings, data.get("cycle"), "cycle"),
        storage=_plain(StorageSettings, data.get("storage"), "storage"),
        gap_rules=_gap_rules(data.get("gap_rules")),
        prioritization=_priority(data.get("prioritization")),
        model=_plain(ModelSettings, data.get("model"), "model"),
        live=_plain(LiveSettings, data.get("live"), "live"),
    )


def load_project_settings(path: Path) -> ProjectSettings:
    with Path(path).open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return project_settings_from_dict(data)
