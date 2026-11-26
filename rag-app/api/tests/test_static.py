from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from rag_api.main import create_app
from rag_api.settings import ApiSettings


def test_static_index_and_health(tmp_path: Path) -> None:
    index = tmp_path / "index.html"
    index.write_text("<!doctype html><title>rag-web</title><h1>ok</h1>", encoding="utf-8")

    settings = ApiSettings(model_mode="fake", web_dist=tmp_path)
    with TestClient(create_app(settings, background=False)) as client:
        home = client.get("/")
        assert home.status_code == 200
        assert "rag-web" in home.text

        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.headers["content-type"].startswith("application/json")
        body = health.json()
        assert "status" in body
