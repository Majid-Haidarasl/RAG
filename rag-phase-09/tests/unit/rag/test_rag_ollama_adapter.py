"""Ollama adapters against a fake local HTTP server (no real Ollama)."""

import pytest

from rag_core.rag.infrastructure.ollama import (
    OllamaChatModel,
    OllamaClient,
    OllamaEmbedder,
    OllamaError,
    OllamaUnavailable,
    require_local,
    strip_think,
)
from tests.fixtures.rag.fakes import FakeOllamaServer

pytestmark = [pytest.mark.rag, pytest.mark.retrieval]


@pytest.mark.parametrize(
    "url", ["http://localhost:11434", "http://127.0.0.1:11434/", "http://[::1]:11434"]
)
def test_local_endpoints_accepted(url: str) -> None:
    assert require_local(url) == url.rstrip("/")


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com:11434",
        "http://10.0.0.5:11434",
        "ftp://localhost",
        "localhost:11434",
    ],
)
def test_remote_endpoints_rejected(url: str) -> None:
    with pytest.raises(OllamaError):
        OllamaClient(url)


@pytest.mark.parametrize(
    "raw,clean",
    [
        ("<think>plan</think>Answer [AR-HR-005 §1]", "Answer [AR-HR-005 §1]"),
        ("<THINK>\nx\n</THINK>\nok", "ok"),
        ("partial reasoning</think>final", "final"),
        ("no tags", "no tags"),
        ("", ""),
    ],
)
def test_strip_think(raw: str, clean: str) -> None:
    assert strip_think(raw) == clean


def test_has_model_matches_latest_tag() -> None:
    names = ["bge-m3:latest", "qwen3:8b"]
    assert OllamaClient.has_model(names, "bge-m3") and OllamaClient.has_model(
        names, "bge-m3:latest"
    )
    assert OllamaClient.has_model(names, "qwen3:8b") and not OllamaClient.has_model(
        names, "qwen3:14b"
    )
    assert not OllamaClient.has_model(["qwen3"], "qwen3:8b")


def test_discovery_and_embedding_batches() -> None:
    with FakeOllamaServer() as srv:
        client = OllamaClient(srv.url, timeout_s=5)
        assert client.version() == "0.40.2-fake"
        assert "qwen3:8b" in client.model_names()
        emb = OllamaEmbedder(
            client, "bge-m3:latest", batch_size=2, num_ctx=4096, timeout_s=5
        )
        vectors = emb.embed(["a", "b", "c", "d", "e"])
        assert len(vectors) == 5 and len(vectors[0]) == 64
        embeds = [b for p, b in srv.requests if p == "/api/embed"]
        assert [len(b["input"]) for b in embeds] == [2, 2, 1]
        assert (
            embeds[0]["model"] == "bge-m3:latest"
            and embeds[0]["options"]["num_ctx"] == 4096
        )


def test_chat_sends_phase2_defaults_and_strips_think() -> None:
    with FakeOllamaServer(
        chat_reply=lambda m: "<think>x</think>جواب [AR-HR-005 §1]"
    ) as srv:
        chat = OllamaChatModel(OllamaClient(srv.url, timeout_s=5))
        res = chat.generate("system", "user")
        body = [b for p, b in srv.requests if p == "/api/chat"][0]
    assert res.text == "جواب [AR-HR-005 §1]" and res.think_used
    assert (
        body["think"] is False
        and body["stream"] is False
        and body["model"] == "qwen3:8b"
    )
    assert body["options"]["temperature"] == 0.2 and body["options"]["num_ctx"] == 8192
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    assert res.prompt_tokens == 120 and res.completion_tokens == 30


def test_chat_falls_back_to_soft_switch_when_think_rejected() -> None:
    with FakeOllamaServer(
        reject_think=True, chat_reply=lambda m: m[-1]["content"][-9:]
    ) as srv:
        res = OllamaChatModel(OllamaClient(srv.url, timeout_s=5)).generate(
            "s", "question"
        )
        bodies = [b for p, b in srv.requests if p == "/api/chat"]
    assert len(bodies) == 2 and "think" not in bodies[1]
    assert res.text == "/no_think"


def test_unreachable_server_raises_unavailable() -> None:
    client = OllamaClient("http://127.0.0.1:9", timeout_s=1, retries=0)
    with pytest.raises(OllamaUnavailable):
        client.version(timeout=0.5)


def test_http_error_reported() -> None:
    with FakeOllamaServer() as srv:
        client = OllamaClient(srv.url, timeout_s=5)
        with pytest.raises(OllamaError, match="404"):
            client._call("GET", "/api/missing")
