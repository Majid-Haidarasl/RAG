from __future__ import annotations

import pytest

from rag_api.runtime import ModelStatus, build_runtime
from rag_api.settings import ApiSettings


@pytest.mark.slow
def test_fake_mode_builds_lexical_runtime(monkeypatch) -> None:
    monkeypatch.setenv("RAG_API_MODEL_MODE", "fake")
    runtime = build_runtime(ApiSettings())
    assert runtime.mode == "lexical"
    assert runtime.can_answer is True
    assert runtime.scope.exists("N-CEO")


@pytest.mark.slow
def test_ollama_unreachable_has_no_service(monkeypatch) -> None:
    monkeypatch.setenv("RAG_API_MODEL_MODE", "ollama")
    unreachable = ModelStatus(
        reachable=False,
        version="",
        base_url="http://localhost:11434",
        installed=[],
        embedding_ok=False,
        generation_ok=False,
        vision_installed=False,
        reason="Ollama not reachable",
    )
    monkeypatch.setattr(
        "rag_api.runtime.probe_models",
        lambda _rag: (None, unreachable),
    )
    runtime = build_runtime(ApiSettings())
    assert runtime.service is None
    assert runtime.mode == "lexical"
