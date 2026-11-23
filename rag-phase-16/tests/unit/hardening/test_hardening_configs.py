"""Phase 15 hardening: config/rag.yaml loader error paths (finding D15-2)."""

from pathlib import Path

import pytest

from rag_core.rag.infrastructure.config import load_settings, settings_from_dict
from rag_core.shared_kernel.errors import InvariantError

pytestmark = [pytest.mark.hardening, pytest.mark.rag]


@pytest.mark.parametrize("value", [[], ""])
def test_empty_non_mapping_section_is_rejected(value: object) -> None:
    with pytest.raises(InvariantError, match="mapping"):
        settings_from_dict({"qa": value})


def test_null_section_uses_defaults() -> None:
    assert settings_from_dict({"qa": None}).qa.prompt_id == "qa.answer"


def test_top_level_must_be_mapping() -> None:
    with pytest.raises(InvariantError, match="mapping of sections"):
        settings_from_dict(["ollama"])  # type: ignore[arg-type]


def test_empty_file_gives_defaults(tmp_path: Path) -> None:
    path = tmp_path / "rag.yaml"
    path.write_text("", encoding="utf-8")
    settings = load_settings(path)
    assert settings.config_version == "0.8.0" and settings.embedding.model == "bge-m3:latest"


def test_unknown_generation_key(tmp_path: Path) -> None:
    path = tmp_path / "rag.yaml"
    path.write_text("generation:\n  modell: qwen3:8b\n", encoding="utf-8")
    with pytest.raises(InvariantError, match="modell"):
        load_settings(path)
