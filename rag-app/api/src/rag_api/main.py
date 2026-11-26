from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from rag_api import __version__
from rag_api.errors import install_error_handlers
from rag_api.holder import RuntimeHolder
from rag_api.routes import router
from rag_api.runtime import RagRuntime, build_runtime
from rag_api.settings import ApiSettings, get_settings

Builder = Callable[[ApiSettings], RagRuntime]


def create_app(
    settings: ApiSettings | None = None,
    builder: Builder | None = None,
    background: bool = True,
) -> FastAPI:
    resolved_settings = settings if settings is not None else get_settings()
    resolved_builder = builder if builder is not None else build_runtime

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        holder = RuntimeHolder(resolved_settings, builder=resolved_builder)
        holder.start(background=background)
        app.state.holder = holder
        app.state.settings = resolved_settings
        yield

    application = FastAPI(
        title="ArmanRayan RAG API",
        version=__version__,
        docs_url="/docs",
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
    return application


app = create_app()
