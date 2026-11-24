"""``config/rfp.yaml`` -> ``RfpSettings`` (unknown keys are rejected)."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml

from rag_core.projects.infrastructure.config import (
    CycleSettings,
    LiveSettings,
    ModelSettings,
)
from rag_core.shared_kernel.errors import InvariantError


@dataclass(frozen=True)
class StorageSettings:
    blueprint_dir: str = "data/rfp"
    proposal_dir: str = "data/proposals"
    prompt_dir: str = "config/prompts/rfp"
    csv_dir: str = "exports/rfp"


@dataclass(frozen=True)
class CandidateSettings:
    categories: tuple[str, ...] = ("procurement",)
    targets: dict[str, str] = field(
        default_factory=lambda: {"AR-ISS-024": "AR-ISS-024/WEB"}
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "categories", tuple(str(c) for c in self.categories))
        targets = {str(k): str(v) for k, v in dict(self.targets or {}).items()}
        for issue, item in targets.items():
            if not item.startswith(issue + "/"):
                raise InvariantError(
                    f"candidates.targets: {item} is not a sub-issue of {issue}"
                )
        object.__setattr__(self, "targets", targets)


@dataclass(frozen=True)
class JudgingSettings:
    max_rfp_chars: int = (
        6000  # an RFP is a document, not a summary (Phase 10 summary limit is 3000)
    )

    def __post_init__(self) -> None:
        if self.max_rfp_chars < 1000:
            raise InvariantError("judging.max_rfp_chars must be >= 1000")


@dataclass(frozen=True)
class RfpLiveSettings(LiveSettings):
    tasks: tuple[str, ...] = ("rfp_summary", "feedback")

    def __post_init__(self) -> None:
        super().__post_init__()
        tasks = tuple(self.tasks)
        if any(t not in {"rfp_summary", "feedback"} for t in tasks):
            raise InvariantError("live.tasks must be rfp_summary and/or feedback")
        object.__setattr__(self, "tasks", tasks)


@dataclass(frozen=True)
class RfpSettings:
    config_version: str = "0.13.0"
    cycle: CycleSettings = field(default_factory=CycleSettings)
    storage: StorageSettings = field(default_factory=StorageSettings)
    candidates: CandidateSettings = field(default_factory=CandidateSettings)
    judging: JudgingSettings = field(default_factory=JudgingSettings)
    model: ModelSettings = field(default_factory=ModelSettings)
    live: RfpLiveSettings = field(default_factory=RfpLiveSettings)


TOP_KEYS = frozenset({f.name for f in fields(RfpSettings)})


def _plain(cls: type, data: Any, section: str) -> Any:
    data = data or {}
    if not isinstance(data, dict):
        raise InvariantError(f"rfp config section {section!r} must be a mapping")
    known = {f.name for f in fields(cls)}
    unknown = sorted(set(data) - known)
    if unknown:
        raise InvariantError(
            f"unknown keys in rfp config {section!r}: {', '.join(unknown)}"
        )
    data = {k: (tuple(v) if isinstance(v, list) else v) for k, v in data.items()}
    for key in ("id", "cutoff"):
        if key in data:
            data[key] = str(data[key])
    return cls(**data)


def rfp_settings_from_dict(data: dict[str, Any]) -> RfpSettings:
    data = data or {}
    unknown = sorted(set(data) - TOP_KEYS)
    if unknown:
        raise InvariantError(f"unknown rfp config sections: {', '.join(unknown)}")
    return RfpSettings(
        config_version=str(data.get("config_version", "0.13.0")),
        cycle=_plain(CycleSettings, data.get("cycle"), "cycle"),
        storage=_plain(StorageSettings, data.get("storage"), "storage"),
        candidates=_plain(CandidateSettings, data.get("candidates"), "candidates"),
        judging=_plain(JudgingSettings, data.get("judging"), "judging"),
        model=_plain(ModelSettings, data.get("model"), "model"),
        live=_plain(RfpLiveSettings, data.get("live"), "live"),
    )


def load_rfp_settings(path: Path) -> RfpSettings:
    with Path(path).open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return rfp_settings_from_dict(data)
