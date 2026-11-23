from __future__ import annotations

from rag_core.executors.domain.model import Executor
from rag_core.shared_kernel.errors import NotFoundError
from rag_core.shared_kernel.identifiers import ExecutorId


class InMemoryExecutorRepository:
    """``ExecutorRepository`` kept in a dict (registry order preserved)."""

    def __init__(self, executors: list[Executor] | None = None) -> None:
        self._items: dict[str, Executor] = {}
        for e in executors or []:
            self.save(e)

    def get(self, executor_id: ExecutorId) -> Executor:
        try:
            return self._items[str(executor_id)]
        except KeyError:
            raise NotFoundError(f"unknown executor {executor_id}") from None

    def list_all(self) -> list[Executor]:
        return list(self._items.values())

    def save(self, executor: Executor) -> None:
        self._items[str(executor.identifier)] = executor

    def by_name(self, name: str) -> Executor:
        """Resolve a person name or alias (``Rouzbeh Mohseni`` → ``Roozbeh Mohseni``)."""
        for e in self._items.values():
            if e.answers_to(name):
                return e
        raise NotFoundError(f"no executor named {name!r}")

    def __len__(self) -> int:
        return len(self._items)
