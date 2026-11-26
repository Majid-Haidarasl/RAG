from __future__ import annotations

from fastapi.testclient import TestClient

from rag_api.main import create_app
from rag_api.settings import ApiSettings


def test_docs_disabled_by_default() -> None:
    settings = ApiSettings(model_mode="fake", docs_enabled=False)
    with TestClient(create_app(settings, background=False)) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404
        assert client.get("/openapi.json").status_code == 404


def test_docs_enabled_exposes_swagger() -> None:
    settings = ApiSettings(model_mode="fake", docs_enabled=True)
    with TestClient(create_app(settings, background=False)) as client:
        assert client.get("/docs").status_code == 200
        assert client.get("/redoc").status_code == 200
        assert client.get("/openapi.json").status_code == 200
