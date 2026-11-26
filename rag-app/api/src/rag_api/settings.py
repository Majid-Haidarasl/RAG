from __future__ import annotations

import functools
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RAG_API_")

    core_root: Path = Path(__file__).resolve().parents[4] / "rag-phase-16"
    model_mode: Literal["ollama", "fake"] = "ollama"
    default_node: str = "N-CEO"
    max_question_chars: int = 2000
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    web_dist: Path | None = None

    @property
    def rag_config_path(self) -> Path:
        return self.core_root / "config" / "rag.yaml"

    @field_validator("core_root")
    @classmethod
    def _require_core_root(cls, value: Path) -> Path:
        root = value.expanduser().resolve()
        if not root.is_dir():
            raise ValueError(f"core_root does not exist or is not a directory: {root}")
        config_path = root / "config" / "rag.yaml"
        if not config_path.is_file():
            raise ValueError(f"rag config not found at {config_path}")
        return root


@functools.lru_cache
def get_settings() -> ApiSettings:
    return ApiSettings()
