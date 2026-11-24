"""Load ``config/rag.yaml`` into typed settings (PyYAML ``safe_load``)."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml

from rag_core.rag.domain.retriever import RetrievalConfig
from rag_core.shared_kernel.errors import InvariantError


@dataclass(frozen=True)
class OllamaSettings:
    base_url: str = "http://localhost:11434"
    connect_timeout_s: float = 3.0
    embed_timeout_s: float = 120.0
    generate_timeout_s: float = 240.0
    keep_alive: str = "30m"
    retries: int = 1


@dataclass(frozen=True)
class EmbeddingSettings:
    model: str = "bge-m3:latest"
    dim: int = 1024
    batch_size: int = 16
    num_ctx: int = 8192


@dataclass(frozen=True)
class GenerationSettings:
    model: str = "qwen3:8b"
    think: bool = False
    options: dict[str, Any] = field(
        default_factory=lambda: {
            "temperature": 0.2,
            "top_p": 0.9,
            "seed": 42,
            "num_ctx": 8192,
            "num_predict": 1024,
        }
    )


@dataclass(frozen=True)
class ContextSettings:
    budget_tokens: int = 3500
    max_block_tokens: int = 900


@dataclass(frozen=True)
class QaSettings:
    prompt_dir: str = "config/prompts/qa"
    prompt_id: str = "qa.answer"
    evidence_min_vector: float = 0.45
    evidence_min_lexical: float = 3.0
    escalate_margin: float = 0.02


@dataclass(frozen=True)
class IndexSettings:
    path: str = ".rag-index/phase-08.sqlite"


@dataclass(frozen=True)
class RagSettings:
    config_version: str = "0.8.0"
    ollama: OllamaSettings = field(default_factory=OllamaSettings)
    embedding: EmbeddingSettings = field(default_factory=EmbeddingSettings)
    generation: GenerationSettings = field(default_factory=GenerationSettings)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    context: ContextSettings = field(default_factory=ContextSettings)
    qa: QaSettings = field(default_factory=QaSettings)
    index: IndexSettings = field(default_factory=IndexSettings)


def _build(cls: type, data: dict[str, Any] | None, section: str) -> Any:
    # ``data or {}`` used to accept an empty list or string silently (Phase 15 finding D15-2).
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise InvariantError(f"config section {section!r} must be a mapping")
    known = {f.name for f in fields(cls)}
    unknown = sorted(set(data) - known)
    if unknown:
        raise InvariantError(f"unknown keys in {section!r}: {', '.join(unknown)}")
    return cls(**data)


def settings_from_dict(data: dict[str, Any]) -> RagSettings:
    if not isinstance(data, dict):
        raise InvariantError("config/rag.yaml must be a mapping of sections")
    sections = {
        "ollama": OllamaSettings,
        "embedding": EmbeddingSettings,
        "generation": GenerationSettings,
        "retrieval": RetrievalConfig,
        "context": ContextSettings,
        "qa": QaSettings,
        "index": IndexSettings,
    }
    unknown = sorted(set(data) - set(sections) - {"config_version"})
    if unknown:
        raise InvariantError(f"unknown config sections: {', '.join(unknown)}")
    built = {name: _build(cls, data.get(name), name) for name, cls in sections.items()}
    return RagSettings(config_version=str(data.get("config_version", "0.8.0")), **built)


def load_settings(path: Path) -> RagSettings:
    with Path(path).open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return settings_from_dict(data)
