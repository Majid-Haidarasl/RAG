from __future__ import annotations

from rag_api.settings import ApiSettings


def test_default_core_root_contains_rag_yaml() -> None:
    settings = ApiSettings()
    assert (settings.core_root / "config" / "rag.yaml").is_file()


def test_default_node_is_adm_hr() -> None:
    settings = ApiSettings()
    assert settings.default_node == "N-ADM-HR"


def test_default_node_from_env(monkeypatch) -> None:
    monkeypatch.setenv("RAG_API_DEFAULT_NODE", "N-CEO")
    settings = ApiSettings()
    assert settings.default_node == "N-CEO"


def test_model_mode_from_env(monkeypatch) -> None:
    monkeypatch.setenv("RAG_API_MODEL_MODE", "fake")
    settings = ApiSettings()
    assert settings.model_mode == "fake"


def test_docs_enabled_default_false() -> None:
    settings = ApiSettings()
    assert settings.docs_enabled is False


def test_docs_enabled_from_env(monkeypatch) -> None:
    monkeypatch.setenv("RAG_API_DOCS", "true")
    settings = ApiSettings()
    assert settings.docs_enabled is True
