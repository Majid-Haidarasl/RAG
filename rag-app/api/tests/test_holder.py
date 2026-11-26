from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest
from rag_core.qa.domain.model import QaRequest

from rag_api.errors import ApiError
from rag_api.holder import RuntimeHolder
from rag_api.settings import ApiSettings


def _settings() -> ApiSettings:
    return ApiSettings()


def test_require_warming_up_then_ready() -> None:
    gate = threading.Event()
    runtime = SimpleNamespace(service=object(), models=SimpleNamespace(reason=""))

    def builder(_settings: ApiSettings) -> SimpleNamespace:
        gate.wait(timeout=5)
        return runtime

    holder = RuntimeHolder(_settings(), builder=builder)  # type: ignore[arg-type]
    holder.start(background=True)

    with pytest.raises(ApiError) as exc_info:
        holder.require()
    assert exc_info.value.code == "warming_up"
    assert exc_info.value.status == 503
    assert holder.state == "loading"

    gate.set()
    assert holder._thread is not None
    holder._thread.join(timeout=5)
    assert holder.state == "ready"
    assert holder.require() is runtime


def test_builder_failure_sets_error_state() -> None:
    def builder(_settings: ApiSettings) -> SimpleNamespace:
        raise RuntimeError("boom")

    holder = RuntimeHolder(_settings(), builder=builder)  # type: ignore[arg-type]
    holder.start(background=False)

    assert holder.state == "error"
    assert holder.error == "boom"
    with pytest.raises(ApiError) as exc_info:
        holder.require()
    assert exc_info.value.code == "startup_failed"
    assert exc_info.value.status == 503
    assert exc_info.value.message == "boom"


def test_ask_model_unavailable_when_service_none() -> None:
    runtime = SimpleNamespace(
        service=None,
        models=SimpleNamespace(reason="Ollama not reachable"),
    )

    def builder(_settings: ApiSettings) -> SimpleNamespace:
        return runtime

    holder = RuntimeHolder(_settings(), builder=builder)  # type: ignore[arg-type]
    holder.start(background=False)

    request = QaRequest(question="سلام", node="N-CEO")
    with pytest.raises(ApiError) as exc_info:
        holder.ask(request)
    assert exc_info.value.code == "model_unavailable"
    assert exc_info.value.status == 503
    assert exc_info.value.message == "Ollama not reachable"
