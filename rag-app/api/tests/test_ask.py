from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from rag_api.main import create_app
from rag_api.runtime import build_runtime
from rag_api.settings import ApiSettings


@pytest.mark.slow
def test_ask_answered_grounded(client: TestClient) -> None:
    response = client.post(
        "/api/ask",
        json={
            "question": "سقف مرخصی ساعتی در روز و در ماه چقدر است؟",
            "node_id": "N-ADM-HR",
        },
    )
    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["status"] == "answered"
    assert body["grounded"] is True
    assert any(source["cited"] is True for source in body["sources"])


@pytest.mark.slow
def test_ask_not_found_in_scope(client: TestClient) -> None:
    response = client.post(
        "/api/ask",
        json={"question": "xqzv blorf plonk", "node_id": "N-CEO"},
    )
    assert response.status_code == 200, response.json()
    assert response.json()["status"] == "not_found_in_scope"


@pytest.mark.slow
def test_ask_unknown_node(client: TestClient) -> None:
    response = client.post(
        "/api/ask",
        json={"question": "سلام", "node_id": "N-NOPE"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "unknown_node"


@pytest.mark.slow
def test_ask_empty_question(client: TestClient) -> None:
    response = client.post(
        "/api/ask",
        json={"question": "   ", "node_id": "N-CEO"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.slow
def test_ask_model_unavailable() -> None:
    settings = ApiSettings(model_mode="fake")

    def builder(api_settings: ApiSettings):
        runtime = build_runtime(api_settings)
        runtime.service = None
        return runtime

    with TestClient(
        create_app(settings, builder=builder, background=False)
    ) as test_client:
        response = test_client.post(
            "/api/ask",
            json={"question": "سلام", "node_id": "N-CEO"},
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "model_unavailable"
