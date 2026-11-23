"""``config/quality.yaml`` -> ``QualitySettings`` (unknown keys are errors)."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml

from rag_core.shared_kernel.errors import InvariantError


@dataclass(frozen=True)
class CoverageSettings:
    report_dir: str = "results/phase-15"
    json_file: str = "coverage.json"
    min_line_pct: float = 80.0
    min_context_pct: float = 0.0
    lowest: int = 10
    min_statements: int = 20
    package: str = "rag_core"

    def __post_init__(self) -> None:
        for name in ("min_line_pct", "min_context_pct"):
            if not 0 <= getattr(self, name) <= 100:
                raise InvariantError(f"coverage.{name} must be within 0..100")
        if self.lowest < 0 or self.min_statements < 0:
            raise InvariantError("coverage.lowest and coverage.min_statements must be >= 0")


@dataclass(frozen=True)
class ReleaseSettings:
    tag: str = "v0.9"
    title: str = "final trial core"
    checklist: str = "config/release-checklist.yaml"
    docs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.tag.startswith("v") or not self.tag[1:].replace(".", "").isdigit():
            raise InvariantError(f"release.tag must look like v0.9, got {self.tag!r}")


@dataclass(frozen=True)
class EvalDefaults:
    phase14_results: str = "eval/results"
    expected: dict[str, str] = field(default_factory=dict)   # kind -> variant config/eval.yaml must select


@dataclass(frozen=True)
class QualitySettings:
    config_version: str = ""
    coverage: CoverageSettings = field(default_factory=CoverageSettings)
    release: ReleaseSettings = field(default_factory=ReleaseSettings)
    eval: EvalDefaults = field(default_factory=EvalDefaults)


def _section(cls: type, data: Any, where: str) -> Any:
    if data is None:
        return cls()
    if not isinstance(data, dict):
        raise InvariantError(f"quality config {where} must be a mapping")
    known = {f.name for f in fields(cls)}
    unknown = sorted(set(data) - known)
    if unknown:
        raise InvariantError(f"unknown keys in quality config {where}: {', '.join(unknown)}")
    values = {k: (tuple(v) if isinstance(v, list) else v) for k, v in data.items()}
    return cls(**values)


def quality_settings_from_dict(data: Any) -> QualitySettings:
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise InvariantError("quality config must be a mapping")
    unknown = sorted(set(data) - {"config_version", "coverage", "release", "eval"})
    if unknown:
        raise InvariantError(f"unknown quality config sections: {', '.join(unknown)}")
    ev = data.get("eval") or {}
    if not isinstance(ev, dict):
        raise InvariantError("quality config eval must be a mapping")
    unknown = sorted(set(ev) - {"phase14_results", "expected"})
    if unknown:
        raise InvariantError(f"unknown keys in quality config eval: {', '.join(unknown)}")
    expected = ev.get("expected") or {}
    if not isinstance(expected, dict):
        raise InvariantError("quality config eval.expected must map kind -> variant")
    return QualitySettings(
        config_version=str(data.get("config_version", "")),
        coverage=_section(CoverageSettings, data.get("coverage"), "coverage"),
        release=_section(ReleaseSettings, data.get("release"), "release"),
        eval=EvalDefaults(str(ev.get("phase14_results", "eval/results")), {str(k): str(v) for k, v in expected.items()}),
    )


def load_quality_settings(path: Path) -> QualitySettings:
    with Path(path).open(encoding="utf-8") as fh:
        return quality_settings_from_dict(yaml.safe_load(fh))
