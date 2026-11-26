from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.mark.slow
def test_health_ready_lexical(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["mode"] == "lexical"
    assert body["can_answer"] is True


@pytest.mark.slow
def test_nodes_list(client: TestClient) -> None:
    response = client.get("/api/nodes")
    assert response.status_code == 200
    body = response.json()
    assert body["default_node_id"] == "N-CEO"
    assert len(body["nodes"]) == 21
    ids = {node["id"] for node in body["nodes"]}
    assert "N-SW-SUP" in ids
