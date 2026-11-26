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
    promote_min_judge_total: int | None = None  # None → judge rubric accept_total


@dataclass(frozen=True)
class EmbeddingDedupSettings:
    same_threshold: float = 0.92
    borderline_low: float = 0.75


@dataclass(frozen=True)
class KnowledgeSettings:
    embedding_dedup: EmbeddingDedupSettings = field(
        default_factory=EmbeddingDedupSettings
    )


@dataclass(frozen=True)
class IndexSettings:
    path: str = ".rag-index/phase-08.sqlite"


@dataclass(frozen=True)
class LvmIngestionSettings:
    enabled: bool = False
    dpi: int = 150
    prompt_dir: str = "config/prompts/lvm"
    prompt_id: str = "lvm.page_text"
    model_id: str = "lvm-qwen2.5vl-3b"
    keep_alive: str = "0"


@dataclass(frozen=True)
class IngestionSettings:
    lvm: LvmIngestionSettings = field(default_factory=LvmIngestionSettings)


@dataclass(frozen=True)
class RagSettings:
    config_version: str = "0.8.0"
    ollama: OllamaSettings = field(default_factory=OllamaSettings)
    embedding: EmbeddingSettings = field(default_factory=EmbeddingSettings)
    generation: GenerationSettings = field(default_factory=GenerationSettings)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    context: ContextSettings = field(default_factory=ContextSettings)
    qa: QaSettings = field(default_factory=QaSettings)
    knowledge: KnowledgeSettings = field(default_factory=KnowledgeSettings)
    index: IndexSettings = field(default_factory=IndexSettings)
    ingestion: IngestionSettings = field(default_factory=IngestionSettings)


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


def _build_ingestion(data: dict[str, Any] | None) -> IngestionSettings:
    if data is None:
        return IngestionSettings()
    if not isinstance(data, dict):
        raise InvariantError("config section 'ingestion' must be a mapping")
    unknown = sorted(set(data) - {"lvm"})
    if unknown:
        raise InvariantError(f"unknown keys in 'ingestion': {', '.join(unknown)}")
    return IngestionSettings(lvm=_build(LvmIngestionSettings, data.get("lvm"), "ingestion.lvm"))


def _build_knowledge(data: dict[str, Any] | None) -> KnowledgeSettings:
    if data is None:
        return KnowledgeSettings()
    if not isinstance(data, dict):
        raise InvariantError("config section 'knowledge' must be a mapping")
    unknown = sorted(set(data) - {"embedding_dedup"})
    if unknown:
        raise InvariantError(f"unknown keys in 'knowledge': {', '.join(unknown)}")
    return KnowledgeSettings(
        embedding_dedup=_build(
            EmbeddingDedupSettings, data.get("embedding_dedup"), "knowledge.embedding_dedup"
        )
    )


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
    unknown = sorted(
        set(data) - set(sections) - {"config_version", "ingestion", "knowledge"}
    )
    if unknown:
        raise InvariantError(f"unknown config sections: {', '.join(unknown)}")
    built = {name: _build(cls, data.get(name), name) for name, cls in sections.items()}
    return RagSettings(
        config_version=str(data.get("config_version", "0.8.0")),
        ingestion=_build_ingestion(data.get("ingestion")),
        knowledge=_build_knowledge(data.get("knowledge")),
        **built,
    )


def load_settings(path: Path) -> RagSettings:
    with Path(path).open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return settings_from_dict(data)
