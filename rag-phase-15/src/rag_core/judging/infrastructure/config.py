"""Load ``config/judge.yaml`` into typed settings (PyYAML ``safe_load``).

The Ollama endpoint, timeouts and retries come from ``config/rag.yaml``
(Phase 8); this file only holds what is specific to the judge.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml

from rag_core.judging.domain.rule_judge import RuleJudgeConfig
from rag_core.shared_kernel.errors import InvariantError


@dataclass(frozen=True)
class JudgeModelSettings:
    model: str = "qwen3:8b"
    think: bool = False
    format: str = "json"
    keep_alive: str = "30m"
    timeout_s: float = 180.0
    options: dict[str, Any] = field(
        default_factory=lambda: {
            "temperature": 0.0,
            "top_p": 1.0,
            "seed": 42,
            "num_ctx": 8192,
            "num_predict": 512,
        }
    )


@dataclass(frozen=True)
class JudgeRunSettings:
    retries: int = 1
    sources_char_budget: int = 6000
    live_calibration: bool = True
    live_negatives: bool = True
    max_live_cases: int = 60


@dataclass(frozen=True)
class JudgeFileSettings:
    rubric: str = "config/prompts/judge/rubric.yaml"
    prompt_dir: str = "config/prompts/judge"
    calibration: str = "data/judge/calibration-set.json"
    parser_cases: str = "data/judge/parser-cases.json"
    phase8_results: str = "results/phase-08"
    phase9_results: str = "results/phase-09"


@dataclass(frozen=True)
class JudgeSettings:
    config_version: str = "0.10.0"
    model: JudgeModelSettings = field(default_factory=JudgeModelSettings)
    run: JudgeRunSettings = field(default_factory=JudgeRunSettings)
    files: JudgeFileSettings = field(default_factory=JudgeFileSettings)
    rules: RuleJudgeConfig = field(default_factory=RuleJudgeConfig)


def _build(cls: type, data: Any, section: str) -> Any:
    data = data or {}
    if not isinstance(data, dict):
        raise InvariantError(f"judge config section {section!r} must be a mapping")
    known = {f.name for f in fields(cls)}
    unknown = sorted(set(data) - known)
    if unknown:
        raise InvariantError(
            f"unknown keys in judge config {section!r}: {', '.join(unknown)}"
        )
    return cls(**data)


def judge_settings_from_dict(data: dict[str, Any]) -> JudgeSettings:
    sections = {
        "model": JudgeModelSettings,
        "run": JudgeRunSettings,
        "files": JudgeFileSettings,
        "rules": RuleJudgeConfig,
    }
    unknown = sorted(set(data) - set(sections) - {"config_version"})
    if unknown:
        raise InvariantError(f"unknown judge config sections: {', '.join(unknown)}")
    built = {name: _build(cls, data.get(name), name) for name, cls in sections.items()}
    return JudgeSettings(
        config_version=str(data.get("config_version", "0.10.0")), **built
    )


def load_judge_settings(path: Path) -> JudgeSettings:
    with Path(path).open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return judge_settings_from_dict(data)
