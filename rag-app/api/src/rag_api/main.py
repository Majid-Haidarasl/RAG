from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from rag_api import __version__
from rag_api.errors import install_error_handlers
from rag_api.holder import RuntimeHolder
from rag_api.routes import router
from rag_api.runtime import RagRuntime, build_runtime
from rag_api.settings import ApiSettings, get_settings

Builder = Callable[[ApiSettings], RagRuntime]


def _configure_logging() -> None:
    rag_logger = logging.getLogger("rag_api")
    if not rag_logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        rag_logger.addHandler(handler)
        rag_logger.propagate = False
    rag_logger.setLevel(logging.INFO)


def create_app(
    settings: ApiSettings | None = None,
    builder: Builder | None = None,
    background: bool = True,
) -> FastAPI:
    _configure_logging()
    resolved_settings = settings if settings is not None else get_settings()
    resolved_builder = builder if builder is not None else build_runtime

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        holder = RuntimeHolder(resolved_settings, builder=resolved_builder)
        holder.start(background=background)
        app.state.holder = holder
        app.state.settings = resolved_settings
        yield

    docs_enabled = resolved_settings.docs_enabled
    application = FastAPI(
        title="ArmanRayan RAG API",
        version=__version__,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
        lifespan=lifespan,
    )
    install_error_handlers(application)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    application.include_router(router)
    web_dist = resolved_settings.web_dist
    if web_dist is not None:
        dist = web_dist.expanduser().resolve()
        if dist.is_dir() and (dist / "index.html").is_file():
            application.mount(
                "/",
                StaticFiles(directory=dist, html=True),
                name="web",
            )
    return application


app = create_app()
