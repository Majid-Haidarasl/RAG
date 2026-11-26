from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from rag_api.main import create_app
from rag_api.settings import ApiSettings


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(
        create_app(ApiSettings(model_mode="fake"), background=False)
    ) as test_client:
        yield test_client
