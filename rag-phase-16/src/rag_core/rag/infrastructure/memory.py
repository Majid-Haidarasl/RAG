from __future__ import annotations

from collections.abc import Iterable

from rag_core.rag.domain.records import ChunkRecord
from rag_core.shared_kernel.errors import InvariantError, NotFoundError


class InMemoryChunkStore:
    def __init__(self, records: Iterable[ChunkRecord] = ()) -> None:
        self._items: dict[str, ChunkRecord] = {}
        for record in records:
            self.add(record)

    def add(self, record: ChunkRecord) -> None:
        if record.key in self._items:
            raise InvariantError(f"duplicate record key {record.key}")
        self._items[record.key] = record

    def get(self, key: str) -> ChunkRecord:
        try:
            return self._items[key]
        except KeyError as exc:
            raise NotFoundError(key) from exc

    def all(self) -> list[ChunkRecord]:
        return list(self._items.values())

    def __len__(self) -> int:
        return len(self._items)
