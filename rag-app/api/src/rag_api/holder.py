from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal

from rag_core.qa.domain.model import QaAnswer, QaRequest

from rag_api.errors import ApiError
from rag_api.runtime import RagRuntime, build_runtime
from rag_api.settings import ApiSettings

logger = logging.getLogger(__name__)

Builder = Callable[[ApiSettings], RagRuntime]


def _record_counts(runtime: RagRuntime) -> tuple[int, int]:
    index = getattr(runtime, "index", None)
    if index is not None:
        return index.records, index.active
    store = getattr(getattr(runtime, "retriever", None), "store", None)
    if store is None:
        return 0, 0
    records = store.all()
    return len(records), sum(1 for record in records if getattr(record, "is_active", False))


class RuntimeHolder:
    def __init__(
        self,
        settings: ApiSettings,
        builder: Builder = build_runtime,
    ) -> None:
        self.settings = settings
        self._builder = builder
        self.state: Literal["loading", "ready", "error"] = "loading"
        self.runtime: RagRuntime | None = None
        self.error: str | None = None
        self.started_at: datetime | None = None
        self.ready_at: datetime | None = None
        self._thread: threading.Thread | None = None
        self._ask_lock = threading.Lock()

    def start(self, background: bool = True) -> None:
        self.state = "loading"
        self.runtime = None
        self.error = None
        self.started_at = datetime.now(UTC)
        self.ready_at = None

        def _run() -> None:
            logger.info("runtime building")
            started = time.perf_counter()
            try:
                runtime = self._builder(self.settings)
            except Exception as exc:  # noqa: BLE001
                logger.info("runtime failed: %s", exc)
                self.error = str(exc)
                self.state = "error"
                return
            records, active = _record_counts(runtime)
            logger.info(
                "runtime ready mode=%s records=%d active=%d seconds=%.3f",
                getattr(runtime, "mode", None),
                records,
                active,
                time.perf_counter() - started,
            )
            self.runtime = runtime
            self.ready_at = datetime.now(UTC)
            self.state = "ready"

        if background:
            self._thread = threading.Thread(target=_run, name="rag-runtime", daemon=True)
            self._thread.start()
        else:
            self._thread = None
            _run()

    def require(self) -> RagRuntime:
        if self.state == "loading":
            raise ApiError(503, "warming_up", "runtime is still loading")
        if self.state == "error":
            raise ApiError(
                503,
                "startup_failed",
                self.error or "runtime startup failed",
            )
        if self.runtime is None:
            raise ApiError(503, "startup_failed", "runtime unavailable")
        return self.runtime

    def ask(self, request: QaRequest) -> QaAnswer:
        runtime = self.require()
        if runtime.service is None:
            raise ApiError(
                503,
                "model_unavailable",
                runtime.models.reason or "model unavailable",
            )
        with self._ask_lock:
            return runtime.service.ask(request)
