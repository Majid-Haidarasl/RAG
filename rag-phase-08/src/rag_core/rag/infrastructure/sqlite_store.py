"""Persistent index in one SQLite file (stdlib ``sqlite3``).

Tables: ``meta`` (key/value), ``chunks`` (record JSON + content hash) and
``vectors`` (float32 blob per key, tagged with the embedding model). A
vector is reused while (key, content_hash, model) is unchanged, so a refresh
only embeds new or edited chunks.
"""

from __future__ import annotations

from array import array
import json
from pathlib import Path
import sqlite3

from rag_core.rag.domain.records import ChunkRecord
from rag_core.rag.domain.vector import InMemoryVectorIndex

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS chunks (key TEXT PRIMARY KEY, content_hash TEXT NOT NULL, record TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS vectors (
    key TEXT PRIMARY KEY, model TEXT NOT NULL, content_hash TEXT NOT NULL, dim INTEGER NOT NULL, vec BLOB NOT NULL
);
"""


class SqliteIndexStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(self.path))
        self._db.executescript(SCHEMA)

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> SqliteIndexStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # meta
    def set_meta(self, key: str, value: str) -> None:
        self._db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, value))
        self._db.commit()

    def get_meta(self, key: str) -> str | None:
        row = self._db.execute(
            "SELECT value FROM meta WHERE key = ?", (key,)
        ).fetchone()
        return None if row is None else row[0]

    # records
    def replace_records(self, records: list[ChunkRecord]) -> None:
        with self._db:
            self._db.execute("DELETE FROM chunks")
            self._db.executemany(
                "INSERT INTO chunks VALUES (?, ?, ?)",
                [
                    (r.key, r.content_hash, json.dumps(r.to_dict(), ensure_ascii=False))
                    for r in records
                ],
            )

    def records(self) -> list[ChunkRecord]:
        rows = self._db.execute("SELECT record FROM chunks ORDER BY key").fetchall()
        return [ChunkRecord.from_dict(json.loads(r[0])) for r in rows]

    # vectors
    def vector_fingerprints(self, model: str) -> dict[str, str]:
        rows = self._db.execute(
            "SELECT key, content_hash FROM vectors WHERE model = ?", (model,)
        ).fetchall()
        return {k: h for k, h in rows}

    def put_vectors(
        self, model: str, items: list[tuple[str, str, list[float]]]
    ) -> None:
        with self._db:
            self._db.executemany(
                "INSERT OR REPLACE INTO vectors VALUES (?, ?, ?, ?, ?)",
                [
                    (key, model, h, len(v), array("f", v).tobytes())
                    for key, h, v in items
                ],
            )

    def delete_vectors(self, keys: list[str]) -> None:
        with self._db:
            self._db.executemany(
                "DELETE FROM vectors WHERE key = ?", [(k,) for k in keys]
            )

    def delete_other_models(self, model: str) -> int:
        with self._db:
            cur = self._db.execute("DELETE FROM vectors WHERE model != ?", (model,))
        return cur.rowcount

    def load_vectors(self, model: str) -> InMemoryVectorIndex:
        index = InMemoryVectorIndex()
        for key, blob in self._db.execute(
            "SELECT key, vec FROM vectors WHERE model = ? ORDER BY key", (model,)
        ):
            vec = array("f")
            vec.frombytes(blob)
            index.upsert(key, vec)
        return index
