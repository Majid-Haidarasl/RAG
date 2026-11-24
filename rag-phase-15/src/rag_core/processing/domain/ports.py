"""Ports of the processing context.

* ``NodeTransferPort`` — builds and reviews one node's package for one step
  (the Knowledge Transfer context's ``TransferService``);
* ``PackageStorePort`` — keeps the latest package per (node, cycle) with its
  history (SQLite in production, a dict in tests).

The processor treats packages as opaque objects with ``accepted``,
``status`` and ``detail_level``.
"""

from __future__ import annotations

from typing import Any, Protocol

from rag_core.processing.domain.plan import ProcessingStep


class PackageLike(Protocol):
    @property
    def accepted(self) -> bool: ...

    @property
    def status(self) -> str: ...

    @property
    def detail_level(self) -> str: ...


class NodeTransferPort(Protocol):
    def transfer(
        self,
        cycle_id: str,
        step: ProcessingStep,
        received: list[Any],
        expected_children: int = 0,
    ) -> Any: ...


class SaveOutcomeLike(Protocol):
    action: str
    revision: int


class PackageStorePort(Protocol):
    def save(self, package: Any) -> Any: ...
