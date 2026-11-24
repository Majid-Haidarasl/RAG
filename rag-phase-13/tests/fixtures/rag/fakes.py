"""Test doubles for Phase 8: no Ollama, no network beyond 127.0.0.1."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
from typing import Callable

from rag_core.models.domain.ports import LlmResult
from rag_core.rag.domain.lexical import lexical_tokens
from rag_core.rag.domain.ports import EscalationRoute
from rag_core.rag.domain.records import ChunkRecord, record_key

DIM = 64

# Cross-language "concepts" so FA and EN texts land near each other.
CONCEPTS = {
    "مرخصی": "leave",
    "leave": "leave",
    "ساعتی": "hourly",
    "hourly": "hourly",
    "اولویت": "priority",
    "priority": "priority",
    "پاسخ": "response",
    "response": "response",
    "تعمیر": "repair",
    "repair": "repair",
    "آذرپخش": "azarpakhsh",
    "azarpakhsh": "azarpakhsh",
}


def _bucket(token: str) -> int:
    return (
        int(hashlib.blake2b(token.encode("utf-8"), digest_size=4).hexdigest(), 16) % DIM
    )


class FakeEmbedder:
    """Deterministic bag-of-concepts vectors; counts calls and texts."""

    def __init__(self, dim: int = DIM) -> None:
        self.dim = dim
        self.calls = 0
        self.texts = 0

    def vector(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for tok in lexical_tokens(text):
            vec[_bucket(CONCEPTS.get(tok, tok)) % self.dim] += 1.0
        if not any(vec):
            vec[0] = 1e-3
        return vec

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        self.texts += len(texts)
        return [self.vector(t) for t in texts]


@dataclass
class FakeChat:
    """Scripted chat model. ``reply`` may be a string or f(system, user) -> str."""

    reply: str | Callable[[str, str], str] = "INSUFFICIENT_CONTEXT nothing"
    calls: list[tuple[str, str]] = field(default_factory=list)

    def generate(self, system: str, user: str) -> LlmResult:
        self.calls.append((system, user))
        text = self.reply(system, user) if callable(self.reply) else self.reply
        return LlmResult(
            text=text, prompt_tokens=len(user) // 4, completion_tokens=len(text) // 4
        )


@dataclass
class FakeScope:
    visible: dict[str, set[str]]
    owners: dict[str, str]
    parents: dict[str, str]  # child -> parent, root has none

    def exists(self, node: str) -> bool:
        return node in self.visible

    def visible_documents(self, node: str) -> frozenset[str]:
        return frozenset(self.visible[node])

    def owner_of(self, document_id: str) -> str | None:
        return self.owners.get(document_id)

    def _chain(self, node: str) -> list[str]:
        out = [node]
        while out[-1] in self.parents:
            out.append(self.parents[out[-1]])
        return out

    def route(self, asking: str, evidence_owners: list[str]) -> EscalationRoute:
        outside = [
            o for o in evidence_owners if o not in self.visible[asking] and o != asking
        ]
        if not outside:
            return EscalationRoute("answer", asking, "in scope")
        common = self._chain(asking)
        for owner in outside:
            chain = set(self._chain(owner))
            common = [c for c in common if c in chain]
        return EscalationRoute(
            "escalate",
            common[0],
            f"evidence owned outside scope by {', '.join(outside)}",
        )


def rec(
    doc: str,
    order: int,
    text: str,
    *,
    lang: str = "fa",
    version: str = "1.0",
    owner: str = "N-A",
    layer: int | None = 3,
    cls: str = "policy",
    status: str = "active",
    version_status: str = "active",
    content_hash: str = "",
    duplicate_of: str = "",
    paragraph: int | None = None,
    heading: str = "",
) -> ChunkRecord:
    return ChunkRecord(
        key=record_key(doc, version, lang, order),
        document_id=doc,
        language=lang,
        version=version,
        order=order,
        text=text,
        heading_path=heading,
        owner_node=owner,
        layer=layer,
        knowledge_class=cls,
        status=status,
        version_status=version_status,
        content_hash=content_hash
        or hashlib.sha256(f"{lang}{text}".encode()).hexdigest(),
        duplicate_of=duplicate_of,
        paragraph=paragraph,
    )


def sample_records() -> list[ChunkRecord]:
    """A tiny ArmanRayan-like corpus: HR (N-HR), support SLA (N-SUP), issue file (N-LIB)."""
    return [
        rec(
            "AR-HR-005",
            1,
            "مرخصی ساعتی حداکثر ۴ ساعت در روز و ۱۶ ساعت در ماه است.",
            owner="N-HR",
            cls="hr_policy",
            paragraph=12,
            heading="۵. مرخصی ساعتی",
        ),
        rec(
            "AR-HR-005",
            2,
            "مرخصی بدون حقوق تا ۳۰ روز با تأیید معاون است.",
            owner="N-HR",
            cls="hr_policy",
        ),
        rec(
            "AR-HR-005",
            1,
            "Hourly leave is limited to 4 hours per day and 16 hours per month.",
            lang="en",
            owner="N-HR",
            cls="hr_policy",
        ),
        rec(
            "AR-SW-022",
            3,
            "اولویت ۱ قطع کامل سرویس است: پاسخ ظرف ۳۰ دقیقه و بازیابی موقت ظرف ۴ ساعت.",
            owner="N-SUP",
            cls="sla",
        ),
        rec(
            "AR-SW-022",
            3,
            "Priority 1 is complete outage: response within 30 minutes and restoration within 4 hours.",
            lang="en",
            owner="N-SUP",
            cls="sla",
        ),
        rec(
            "AR-ISS-024",
            5,
            "تأخیر تحویل آذرپخش ناشی از ناسازگاری کنترلر RAID و حافظه RAM با کلاینت ویندوز است.",
            owner="N-LIB",
            layer=4,
            cls="issue_file",
        ),
        rec(
            "AR-ISS-024",
            5,
            "The Azarpakhsh delay comes from RAID controller and RAM mismatch with the Windows client.",
            lang="en",
            owner="N-LIB",
            layer=4,
            cls="issue_file",
        ),
        rec(
            "AR-HW-012",
            7,
            "Level 1 repair is completed within four working hours of accepted intake.",
            lang="en",
            owner="N-REP",
            cls="hw_procedure",
        ),
        rec(
            "AR-HW-012",
            7,
            "Old rule: level 1 repair within three working days.",
            lang="en",
            version="0.9",
            owner="N-REP",
            cls="hw_procedure",
            status="retired",
            version_status="superseded",
        ),
    ]


def sample_scope() -> FakeScope:
    docs = {"AR-HR-005", "AR-SW-022", "AR-ISS-024", "AR-HW-012"}
    return FakeScope(
        visible={
            "N-CEO": set(docs),
            "N-HR": {"AR-HR-005", "AR-ISS-024"},
            "N-SUP": {"AR-SW-022", "AR-ISS-024"},
            "N-REP": {"AR-HW-012", "AR-ISS-024"},
            "N-LIB": {"AR-ISS-024"},
        },
        owners={
            "AR-HR-005": "N-HR",
            "AR-SW-022": "N-SUP",
            "AR-ISS-024": "N-LIB",
            "AR-HW-012": "N-REP",
        },
        parents={
            "N-HR": "N-ADM",
            "N-ADM": "N-CEO",
            "N-SUP": "N-SW",
            "N-SW": "N-CEO",
            "N-REP": "N-HW",
            "N-HW": "N-CEO",
            "N-LIB": "N-CEO",
        },
    )


class FakeOllamaServer:
    """Minimal local stand-in for the Ollama HTTP API (127.0.0.1, random port)."""

    def __init__(
        self,
        models: tuple[str, ...] = ("bge-m3:latest", "qwen3:8b"),
        *,
        reject_think: bool = False,
        chat_reply: Callable[[list[dict]], str] | None = None,
        dim: int = DIM,
    ) -> None:
        self.models = models
        self.reject_think = reject_think
        self.chat_reply = chat_reply or (
            lambda messages: "<think>hidden</think>INSUFFICIENT_CONTEXT none"
        )
        self.embedder = FakeEmbedder(dim)
        self.requests: list[tuple[str, dict]] = []
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: object) -> None:  # silence
                return

            def _send(self, code: int, body: dict) -> None:
                data = json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self) -> None:  # noqa: N802
                server.requests.append((self.path, {}))
                if self.path == "/api/version":
                    self._send(200, {"version": "0.40.2-fake"})
                elif self.path == "/api/tags":
                    self._send(200, {"models": [{"name": m} for m in server.models]})
                else:
                    self._send(404, {"error": "not found"})

            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length) or b"{}")
                server.requests.append((self.path, body))
                if self.path == "/api/embed":
                    texts = (
                        body["input"]
                        if isinstance(body["input"], list)
                        else [body["input"]]
                    )
                    self._send(200, {"embeddings": server.embedder.embed(texts)})
                elif self.path == "/api/chat":
                    if server.reject_think and "think" in body:
                        self._send(400, {"error": "think value not supported"})
                        return
                    self._send(
                        200,
                        {
                            "message": {
                                "role": "assistant",
                                "content": server.chat_reply(body["messages"]),
                            },
                            "prompt_eval_count": 120,
                            "eval_count": 30,
                            "done": True,
                        },
                    )
                else:
                    self._send(404, {"error": "not found"})

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def __enter__(self) -> FakeOllamaServer:
        self.thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
