from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

_NODE_ID_RE = re.compile(r"^N-[A-Z0-9-]+$")


class ModelInfo(BaseModel):
    role: Literal["embedding", "generation", "vision"]
    name: str
    installed: bool
    required: bool


class OllamaInfo(BaseModel):
    reachable: bool
    version: str | None
    base_url: str
    reason: str | None
    models: list[ModelInfo]


class IndexInfo(BaseModel):
    records: int
    active: int
    embedded: int
    reused: int
    dim: int | None
    seconds: float


class HealthResponse(BaseModel):
    status: Literal["loading", "ready", "degraded", "error"]
    mode: Literal["hybrid", "lexical", "fake"] | None
    can_answer: bool
    core_version: str
    api_version: str
    error: str | None
    ollama: OllamaInfo | None
    index: IndexInfo | None


class NodeOut(BaseModel):
    id: str
    name_fa: str
    name_en: str
    node_type: str
    layer: int
    parent_id: str | None


class NodesResponse(BaseModel):
    default_node_id: str
    nodes: list[NodeOut]


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    node_id: str
    top_k: int | None = Field(default=None, ge=1, le=10)

    @field_validator("question", mode="before")
    @classmethod
    def _strip_question(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("node_id")
    @classmethod
    def _normalize_node_id(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not _NODE_ID_RE.fullmatch(normalized):
            raise ValueError("node_id must match ^N-[A-Z0-9-]+$")
        return normalized


class CitationOut(BaseModel):
    label: str
    valid: bool
    granularity: str | None
    reason: str | None


class SourceOut(BaseModel):
    label: str
    key: str
    document_id: str
    title_fa: str
    title_en: str
    version: str
    language: str
    order: int
    heading_path: list[str]
    page: int | None
    paragraph: int | None
    excerpt: str
    cited: bool


class EscalationOut(BaseModel):
    target: str
    target_name_fa: str | None
    reason: str


class AskResponse(BaseModel):
    status: Literal[
        "answered",
        "insufficient_context",
        "not_found_in_scope",
        "out_of_scope",
    ]
    grounded: bool
    text: str
    language: str
    node_id: str
    node_name_fa: str | None
    citations: list[CitationOut]
    sources: list[SourceOut]
    escalation: EscalationOut | None
    fact_flags: list[str]
    model: str | None
    prompt_version: str | None
    timings_s: dict[str, float]


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody
