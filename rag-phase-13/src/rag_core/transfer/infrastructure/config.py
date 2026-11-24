"""``config/transfer.yaml`` → ``TransferSettings`` (unknown keys are rejected)."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml

from rag_core.shared_kernel.errors import InvariantError


@dataclass(frozen=True)
class CycleSettings:
    id: str = "1403-Q2"
    period_start: str = "1403-04-01"
    period_end: str = "1403-06-31"
    trigger: str = "quarter close"


@dataclass(frozen=True)
class StorageSettings:
    db: str = "exports/transfer-packages/transfer-packages.sqlite"
    csv_dir: str = "exports/transfer-packages"


@dataclass(frozen=True)
class SuggestionModelSettings:
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
    max_packages: int = 6
    llm_judge: bool = True

    def __post_init__(self) -> None:
        langs = tuple(self.languages)
        if not langs or any(lang not in {"fa", "en"} for lang in langs):
            raise InvariantError("live.languages must be a non-empty list of fa / en")
        object.__setattr__(self, "languages", langs)
        if self.max_packages < 0:
            raise InvariantError("live.max_packages must be >= 0")


@dataclass(frozen=True)
class UpdateCheckSettings:
    node: str = "N-HW-REP"
    item: str = "AR-ISS-024/HW"
    status: str = "resolved"


@dataclass(frozen=True)
class TransferSettings:
    config_version: str = "0.11.0"
    case: str = "AR-ISS-024"
    cycle: CycleSettings = field(default_factory=CycleSettings)
    storage: StorageSettings = field(default_factory=StorageSettings)
    model: SuggestionModelSettings = field(default_factory=SuggestionModelSettings)
    live: LiveSettings = field(default_factory=LiveSettings)
    update_check: UpdateCheckSettings = field(default_factory=UpdateCheckSettings)


SECTIONS: dict[str, type] = {
    "cycle": CycleSettings,
    "storage": StorageSettings,
    "model": SuggestionModelSettings,
    "live": LiveSettings,
    "update_check": UpdateCheckSettings,
}


def _build(cls: type, data: Any, section: str) -> Any:
    data = data or {}
    if not isinstance(data, dict):
        raise InvariantError(f"transfer config section {section!r} must be a mapping")
    known = {f.name for f in fields(cls)}
    unknown = sorted(set(data) - known)
    if unknown:
        raise InvariantError(
            f"unknown keys in transfer config {section!r}: {', '.join(unknown)}"
        )
    if "id" in data:
        data = {**data, "id": str(data["id"])}
    return cls(**data)


def transfer_settings_from_dict(data: dict[str, Any]) -> TransferSettings:
    unknown = sorted(set(data) - set(SECTIONS) - {"config_version", "case"})
    if unknown:
        raise InvariantError(f"unknown transfer config sections: {', '.join(unknown)}")
    built = {name: _build(cls, data.get(name), name) for name, cls in SECTIONS.items()}
    return TransferSettings(
        config_version=str(data.get("config_version", "0.11.0")),
        case=str(data.get("case", "AR-ISS-024")),
        **built,
    )


def load_transfer_settings(path: Path) -> TransferSettings:
    with Path(path).open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return transfer_settings_from_dict(data)
