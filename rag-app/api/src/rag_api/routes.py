from __future__ import annotations

from typing import Annotated, Literal

import rag_core
from fastapi import APIRouter, Depends, Request

from rag_api import __version__ as api_version
from rag_api.holder import RuntimeHolder
from rag_api.runtime import RagRuntime
from rag_api.schemas import (
    HealthResponse,
    IndexInfo,
    ModelInfo,
    NodeOut,
    NodesResponse,
    OllamaInfo,
)

router = APIRouter(prefix="/api")

_VISION_MODEL = "qwen2.5vl:3b"


def get_holder(request: Request) -> RuntimeHolder:
    return request.app.state.holder


HolderDep = Annotated[RuntimeHolder, Depends(get_holder)]


def _ollama_info(runtime: RagRuntime) -> OllamaInfo:
    models = runtime.models
    rag = runtime.rag
    return OllamaInfo(
        reachable=models.reachable,
        version=models.version or None,
        base_url=models.base_url,
        reason=models.reason or None,
        models=[
            ModelInfo(
                role="embedding",
                name=rag.embedding.model,
                installed=models.embedding_ok,
                required=True,
            ),
            ModelInfo(
                role="generation",
                name=rag.generation.model,
                installed=models.generation_ok,
                required=True,
            ),
            ModelInfo(
                role="vision",
                name=_VISION_MODEL,
                installed=models.vision_installed,
                required=False,
            ),
        ],
    )


def _index_info(runtime: RagRuntime) -> IndexInfo | None:
    index = runtime.index
    if index is None:
        return None
    return IndexInfo(
        records=index.records,
        active=index.active,
        embedded=index.embedded,
        reused=index.reused,
        dim=index.dim,
        seconds=index.seconds,
    )


@router.get("/health", response_model=HealthResponse)
def health(holder: HolderDep) -> HealthResponse:
    core_version = rag_core.__version__
    if holder.state == "loading":
        return HealthResponse(
            status="loading",
            mode=None,
            can_answer=False,
            core_version=core_version,
            api_version=api_version,
            error=None,
            ollama=None,
            index=None,
        )
    if holder.state == "error":
        return HealthResponse(
            status="error",
            mode=None,
            can_answer=False,
            core_version=core_version,
            api_version=api_version,
            error=holder.error,
            ollama=None,
            index=None,
        )

    runtime = holder.runtime
    assert runtime is not None
    mode: Literal["hybrid", "lexical"] | None
    mode = runtime.mode if runtime.mode in ("hybrid", "lexical") else None
    return HealthResponse(
        status="ready" if runtime.can_answer else "degraded",
        mode=mode,
        can_answer=runtime.can_answer,
        core_version=core_version,
        api_version=api_version,
        error=None,
        ollama=_ollama_info(runtime),
        index=_index_info(runtime),
    )


@router.get("/nodes", response_model=NodesResponse)
def nodes(holder: HolderDep) -> NodesResponse:
    runtime = holder.require()
    active = sorted(
        runtime.scope.org.active_nodes(),
        key=lambda node: (int(node.layer.value), str(node.identifier)),
    )
    return NodesResponse(
        default_node_id=holder.settings.default_node,
        nodes=[
            NodeOut(
                id=str(node.identifier),
                name_fa=node.name_fa,
                name_en=node.name_en,
                node_type=node.node_type.value,
                layer=int(node.layer.value),
                parent_id=str(node.parent_id) if node.parent_id else None,
            )
            for node in active
        ],
    )
