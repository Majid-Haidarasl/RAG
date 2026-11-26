from __future__ import annotations

import logging
from typing import Annotated, Literal

import rag_core
from fastapi import APIRouter, Depends, Request
from rag_core.qa.domain.model import QaRequest
from rag_core.rag.infrastructure.ollama import OllamaError, OllamaUnavailable
from rag_core.shared_kernel.errors import InvariantError

from rag_api import __version__ as api_version
from rag_api.errors import ApiError
from rag_api.holder import RuntimeHolder
from rag_api.mapping import to_ask_response
from rag_api.runtime import RagRuntime
from rag_api.schemas import (
    AskRequest,
    AskResponse,
    HealthResponse,
    IndexInfo,
    ModelInfo,
    NodeOut,
    NodesResponse,
    OllamaInfo,
)

logger = logging.getLogger(__name__)

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


@router.post("/ask", response_model=AskResponse)
def ask(body: AskRequest, holder: HolderDep) -> AskResponse:
    runtime = holder.require()
    if not runtime.scope.exists(body.node_id):
        raise ApiError(404, "unknown_node", f"unknown node {body.node_id}")
    try:
        answer = holder.ask(QaRequest(body.question, body.node_id, top_k=body.top_k))
    except ApiError:
        raise
    except OllamaUnavailable as exc:
        raise ApiError(503, "model_unavailable", str(exc)) from exc
    except OllamaError as exc:
        raise ApiError(502, "model_error", str(exc)) from exc
    except InvariantError as exc:
        raise ApiError(422, "validation_error", str(exc)) from exc

    logger.info(
        "ask node=%s status=%s total_s=%.3f",
        body.node_id,
        answer.status.value,
        answer.timings_s.get("total", 0.0),
    )
    return to_ask_response(answer, runtime)
