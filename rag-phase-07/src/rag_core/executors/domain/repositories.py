from __future__ import annotations

from typing import Protocol

from rag_core.executors.domain.model import Executor
from rag_core.shared_kernel.identifiers import ExecutorId


class ExecutorRepository(Protocol):
    def get(self, executor_id: ExecutorId) -> Executor: ...
    def list_all(self) -> list[Executor]: ...
    def save(self, executor: Executor) -> None: ...
