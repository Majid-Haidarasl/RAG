from __future__ import annotations

from rag_api.settings import ApiSettings


def test_default_core_root_contains_rag_yaml() -> None:
    settings = ApiSettings()
    assert (settings.core_root / "config" / "rag.yaml").is_file()


def test_model_mode_from_env(monkeypatch) -> None:
    monkeypatch.setenv("RAG_API_MODEL_MODE", "fake")
    settings = ApiSettings()
    assert settings.model_mode == "fake"
