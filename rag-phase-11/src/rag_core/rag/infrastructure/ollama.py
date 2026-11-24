"""Local Ollama adapters over the HTTP API (stdlib ``urllib`` only).

Phase 2 contract: the endpoint must be the local machine. Any other host is
rejected before a socket is opened. Generation runs with ``think: false``;
if an older server rejects the field, the qwen3 soft switch ``/no_think`` is
appended instead, and any ``<think>…</think>`` text is stripped from replies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
import socket
import time
from typing import Any
from urllib import error, request
from urllib.parse import urlparse

from rag_core.models.domain.ports import LlmResult

LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_THINK_RE = re.compile(r"<think>.*?</think>", re.S | re.I)


class OllamaError(RuntimeError):
    pass


class OllamaUnavailable(OllamaError):
    """Server not reachable (connection refused, timeout, DNS)."""


def strip_think(text: str) -> str:
    out = _THINK_RE.sub("", text or "")
    if "</think>" in out:  # unterminated opening tag
        out = out.split("</think>", 1)[1]
    return out.replace("<think>", "").strip()


def require_local(base_url: str) -> str:
    parsed = urlparse(base_url)
    if (
        parsed.scheme not in {"http", "https"}
        or (parsed.hostname or "") not in LOCAL_HOSTS
    ):
        raise OllamaError(
            f"Ollama endpoint must be local (localhost / 127.0.0.1), got {base_url!r}"
        )
    return base_url.rstrip("/")


@dataclass
class OllamaClient:
    base_url: str = "http://localhost:11434"
    timeout_s: float = 300.0
    retries: int = 1
    calls: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self.base_url = require_local(self.base_url)

    def _call(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            req = request.Request(
                self.base_url + path,
                data=data,
                method=method,
                headers={"Content-Type": "application/json"},
            )
            try:
                self.calls += 1
                with request.urlopen(req, timeout=timeout or self.timeout_s) as resp:  # noqa: S310 (local only)
                    body = resp.read().decode("utf-8")
                return json.loads(body) if body.strip() else {}
            except error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")[:300]
                raise OllamaError(f"HTTP {exc.code} {path}: {detail}") from None
            except (
                error.URLError,
                socket.timeout,
                TimeoutError,
                ConnectionError,
            ) as exc:
                last = exc
                if attempt < self.retries:
                    time.sleep(1.0 + attempt)
        raise OllamaUnavailable(f"{path}: {type(last).__name__}: {last}")

    # -- discovery -------------------------------------------------------------
    def version(self, timeout: float = 3.0) -> str:
        return str(
            self._call("GET", "/api/version", timeout=timeout).get("version", "")
        )

    def model_names(self, timeout: float = 10.0) -> list[str]:
        return [
            m.get("name", "")
            for m in self._call("GET", "/api/tags", timeout=timeout).get("models", [])
        ]

    @staticmethod
    def has_model(names: list[str], wanted: str) -> bool:
        if wanted in names:
            return True
        base = wanted.split(":", 1)[0]
        tag = wanted.split(":", 1)[1] if ":" in wanted else "latest"
        return any(
            n.split(":", 1)[0] == base
            and (n.split(":", 1)[1] if ":" in n else "latest") == tag
            for n in names
        )

    # -- inference ---------------------------------------------------------------
    def embed(
        self,
        model: str,
        texts: list[str],
        *,
        keep_alive: str = "30m",
        num_ctx: int = 8192,
        timeout: float | None = None,
    ) -> list[list[float]]:
        out = self._call(
            "POST",
            "/api/embed",
            {
                "model": model,
                "input": texts,
                "keep_alive": keep_alive,
                "options": {"num_ctx": num_ctx},
            },
            timeout=timeout,
        )
        vectors = out.get("embeddings") or []
        if len(vectors) != len(texts):
            raise OllamaError(
                f"/api/embed returned {len(vectors)} vectors for {len(texts)} texts"
            )
        return vectors

    def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        options: dict[str, Any] | None = None,
        think: bool = False,
        keep_alive: str = "30m",
        timeout: float | None = None,
        response_format: str | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "keep_alive": keep_alive,
            "options": options or {},
            "think": think,
        }
        if response_format:  # Phase 10 judge: "json" asks Ollama for a JSON reply
            payload["format"] = response_format
        try:
            return self._call("POST", "/api/chat", payload, timeout=timeout)
        except OllamaError as exc:
            if "think" not in str(exc).lower() or isinstance(exc, OllamaUnavailable):
                raise
            payload.pop("think")
            msgs = [dict(m) for m in messages]
            msgs[-1]["content"] += "\n/think" if think else "\n/no_think"
            payload["messages"] = msgs
            return self._call("POST", "/api/chat", payload, timeout=timeout)


@dataclass
class OllamaEmbedder:
    """``EmbeddingPort`` for bge-m3. Batches keep VRAM and request size modest."""

    client: OllamaClient
    model: str = "bge-m3:latest"
    batch_size: int = 16
    num_ctx: int = 8192
    keep_alive: str = "30m"
    timeout_s: float = 120.0

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            out.extend(
                self.client.embed(
                    self.model,
                    texts[i : i + self.batch_size],
                    keep_alive=self.keep_alive,
                    num_ctx=self.num_ctx,
                    timeout=self.timeout_s,
                )
            )
        return out


@dataclass
class OllamaChatModel:
    """``ChatModelPort`` for qwen3:8b with Phase 2 defaults (think off)."""

    client: OllamaClient
    model: str = "qwen3:8b"
    options: dict[str, Any] = field(
        default_factory=lambda: {
            "temperature": 0.2,
            "top_p": 0.9,
            "seed": 42,
            "num_ctx": 8192,
            "num_predict": 1024,
        }
    )
    think: bool = False
    keep_alive: str = "30m"
    timeout_s: float = 240.0
    response_format: str | dict[str, Any] | None = (
        None  # None for answers; "json" for the Phase 10 judge
    )

    def generate(self, system: str, user: str) -> LlmResult:
        res = self.client.chat(
            self.model,
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            options=self.options,
            think=self.think,
            keep_alive=self.keep_alive,
            timeout=self.timeout_s,
            response_format=self.response_format,
        )
        message = res.get("message") or {}
        raw = message.get("content", "")
        return LlmResult(
            text=strip_think(raw),
            prompt_tokens=int(res.get("prompt_eval_count") or 0),
            completion_tokens=int(res.get("eval_count") or 0),
            think_used=bool(message.get("thinking")) or "<think>" in raw,
        )
