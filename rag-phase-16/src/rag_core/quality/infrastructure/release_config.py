"""``config/release.yaml`` -> ``ReleaseCheckSettings`` (unknown keys are errors)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from rag_core.quality.domain.release import DocRequirement, require_version
from rag_core.shared_kernel.errors import InvariantError

TOP_KEYS = {"config_version", "version", "tag", "title", "docs", "changelog", "presentation", "evidence",
            "scan", "versions", "eval"}


@dataclass(frozen=True)
class ChangelogSettings:
    path: str = "CHANGELOG.md"
    versions: tuple[str, ...] = ()


@dataclass(frozen=True)
class PresentationSettings:
    path: str = "presentation/armanrayan-rag-core.pptx"
    source: str = "presentation/build_slides.js"
    min_slides: int = 10
    max_slides: int = 12


@dataclass(frozen=True)
class EvidenceItem:
    name: str
    pattern: str          # glob relative to the kit root, e.g. results/phase-08/rag-demo-*.json


@dataclass(frozen=True)
class ScanSettings:
    suffixes: tuple[str, ...] = (".md", ".py", ".sh", ".yaml", ".yml", ".toml", ".txt")
    exclude: tuple[str, ...] = ()     # folder or file paths relative to the kit root
    phrases: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReleaseCheckSettings:
    config_version: str
    version: str
    tag: str
    title: str = ""
    docs: tuple[DocRequirement, ...] = ()
    changelog: ChangelogSettings = field(default_factory=ChangelogSettings)
    presentation: PresentationSettings = field(default_factory=PresentationSettings)
    evidence: tuple[EvidenceItem, ...] = ()
    scan: ScanSettings = field(default_factory=ScanSettings)
    versions: dict[str, str] = field(default_factory=dict)   # where -> how ("pyproject", "package", "yaml:<key>")
    eval_expected: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_version(self.version, "release.version")
        if not self.tag.startswith("v") or not self.tag[1:].replace(".", "").isdigit():
            raise InvariantError(f"release tag must look like v1.0, got {self.tag!r}")


def _mapping(data: Any, where: str, keys: set[str]) -> dict[str, Any]:
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise InvariantError(f"release config {where} must be a mapping")
    unknown = sorted(set(data) - keys)
    if unknown:
        raise InvariantError(f"unknown keys in release config {where}: {', '.join(unknown)}")
    return data


def _strings(value: Any, where: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise InvariantError(f"release config {where} must be a list")
    return tuple(str(v) for v in value)


def release_settings_from_dict(data: Any) -> ReleaseCheckSettings:
    top = _mapping(data, "file", TOP_KEYS)
    if not top:
        raise InvariantError("release config is empty")
    docs = []
    for i, d in enumerate(top.get("docs") or []):
        d = _mapping(d, f"docs[{i}]", {"path", "min_chars", "markers"})
        docs.append(DocRequirement(str(d.get("path", "")), int(d.get("min_chars", 400)),
                                   _strings(d.get("markers"), f"docs[{i}].markers")))
    ch = _mapping(top.get("changelog"), "changelog", {"path", "versions"})
    pr = _mapping(top.get("presentation"), "presentation", {"path", "source", "min_slides", "max_slides"})
    sc = _mapping(top.get("scan"), "scan", {"suffixes", "exclude", "phrases"})
    evidence = []
    for i, e in enumerate(top.get("evidence") or []):
        e = _mapping(e, f"evidence[{i}]", {"name", "pattern"})
        if not e.get("name") or not e.get("pattern"):
            raise InvariantError(f"evidence[{i}] needs name and pattern")
        evidence.append(EvidenceItem(str(e["name"]), str(e["pattern"])))
    versions = top.get("versions") or {}
    if not isinstance(versions, dict):
        raise InvariantError("release config versions must map file -> source")
    bad = sorted(str(k) for k, v in versions.items() if str(v) not in ("pyproject", "package")
                 and not str(v).startswith("yaml:"))
    if bad:
        raise InvariantError(f"release config versions: unknown source for {', '.join(bad)}")
    ev = _mapping(top.get("eval"), "eval", {"expected"})
    expected = ev.get("expected") or {}
    if not isinstance(expected, dict):
        raise InvariantError("release config eval.expected must map kind -> variant")
    return ReleaseCheckSettings(
        config_version=str(top.get("config_version", "")),
        version=str(top.get("version", "")),
        tag=str(top.get("tag", "")),
        title=str(top.get("title", "")),
        docs=tuple(docs),
        changelog=ChangelogSettings(str(ch.get("path", "CHANGELOG.md")), _strings(ch.get("versions"), "changelog.versions")),
        presentation=PresentationSettings(str(pr.get("path", PresentationSettings.path)),
                                          str(pr.get("source", PresentationSettings.source)),
                                          int(pr.get("min_slides", 10)), int(pr.get("max_slides", 12))),
        evidence=tuple(evidence),
        scan=ScanSettings(_strings(sc.get("suffixes"), "scan.suffixes") or ScanSettings.suffixes,
                          _strings(sc.get("exclude"), "scan.exclude"), _strings(sc.get("phrases"), "scan.phrases")),
        versions={str(k): str(v) for k, v in versions.items()},
        eval_expected={str(k): str(v) for k, v in expected.items()},
    )


def load_release_settings(path: Path) -> ReleaseCheckSettings:
    with Path(path).open(encoding="utf-8") as fh:
        return release_settings_from_dict(yaml.safe_load(fh))
