"""SQLite persistence of the latest TransferPackage per (cycle, source node), with history.

Saving is idempotent: the same content (same SHA-256 of the canonical JSON)
for the same (cycle, node) stores nothing new (``unchanged``). Different
content adds the next revision, marks it latest and keeps the earlier ones
(``updated``). Only the ``is_latest`` rows are exported to CSV.
AI suggestions are kept in their own table with the same rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any

from rag_core.transfer.domain.review import PackageRecord, content_hash

SCHEMA_VERSION = "1"
SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS transfer_packages (
    cycle_id TEXT NOT NULL,
    source_node TEXT NOT NULL,
    revision INTEGER NOT NULL,
    is_latest INTEGER NOT NULL,
    target_node TEXT NOT NULL,
    target_layer INTEGER NOT NULL,
    detail_level TEXT NOT NULL,
    status TEXT NOT NULL,
    words_en INTEGER NOT NULL,
    words_fa INTEGER NOT NULL,
    items INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (cycle_id, source_node, revision)
);
CREATE INDEX IF NOT EXISTS ix_packages_latest ON transfer_packages (cycle_id, is_latest);
CREATE TABLE IF NOT EXISTS transfer_suggestions (
    cycle_id TEXT NOT NULL,
    source_node TEXT NOT NULL,
    language TEXT NOT NULL,
    revision INTEGER NOT NULL,
    is_latest INTEGER NOT NULL,
    status TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (cycle_id, source_node, language, revision)
);
"""


@dataclass(frozen=True)
class SaveOutcome:
    action: str  # inserted | unchanged | updated
    revision: int
    content_hash: str


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class SqliteTransferStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        with self.conn:
            self.conn.execute(
                "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', ?)",
                (SCHEMA_VERSION,),
            )

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> SqliteTransferStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- packages -------------------------------------------------------------
    def save(self, package: Any) -> SaveOutcome:
        record: PackageRecord = (
            package.to_record() if hasattr(package, "to_record") else package
        )
        latest = self.conn.execute(
            "SELECT revision, content_hash FROM transfer_packages WHERE cycle_id=? AND source_node=? AND is_latest=1",
            (record.cycle_id, record.source_node),
        ).fetchone()
        if latest is not None and latest["content_hash"] == record.content_hash:
            return SaveOutcome(
                "unchanged", int(latest["revision"]), record.content_hash
            )
        revision = 1 if latest is None else int(latest["revision"]) + 1
        with self.conn:
            self.conn.execute(
                "UPDATE transfer_packages SET is_latest=0 WHERE cycle_id=? AND source_node=?",
                (record.cycle_id, record.source_node),
            )
            self.conn.execute(
                "INSERT INTO transfer_packages (cycle_id, source_node, revision, is_latest, target_node, target_layer, "
                "detail_level, status, words_en, words_fa, items, content_hash, created_at, payload) "
                "VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.cycle_id,
                    record.source_node,
                    revision,
                    record.target_node,
                    record.target_layer,
                    record.detail_level,
                    record.status,
                    record.words_en,
                    record.words_fa,
                    record.items,
                    record.content_hash,
                    _now(),
                    json.dumps(record.payload, ensure_ascii=False, sort_keys=True),
                ),
            )
        return SaveOutcome(
            "inserted" if latest is None else "updated", revision, record.content_hash
        )

    def latest(self, cycle_id: str, source_node: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM transfer_packages WHERE cycle_id=? AND source_node=? AND is_latest=1",
            (cycle_id, source_node),
        ).fetchone()
        return self._row(row) if row is not None else None

    def latest_all(self, cycle_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM transfer_packages WHERE cycle_id=? AND is_latest=1 "
            "ORDER BY target_layer DESC, source_node",
            (cycle_id,),
        ).fetchall()
        return [self._row(r) for r in rows]

    def history(self, cycle_id: str, source_node: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT revision, is_latest, status, content_hash, created_at FROM transfer_packages "
            "WHERE cycle_id=? AND source_node=? ORDER BY revision",
            (cycle_id, source_node),
        ).fetchall()
        return [dict(r) for r in rows]

    def stats(self, cycle_id: str | None = None) -> dict[str, int]:
        where, args = ("WHERE cycle_id=?", (cycle_id,)) if cycle_id else ("", ())
        rows = self.conn.execute(
            f"SELECT COUNT(*) AS n, COALESCE(SUM(is_latest), 0) AS latest, "
            f"COALESCE(MAX(revision), 0) AS max_revision FROM transfer_packages {where}",
            args,
        ).fetchone()
        cycles = self.conn.execute(
            "SELECT COUNT(DISTINCT cycle_id) AS c FROM transfer_packages"
        ).fetchone()
        return {
            "rows": int(rows["n"]),
            "latest": int(rows["latest"]),
            "max_revision": int(rows["max_revision"]),
            "cycles": int(cycles["c"]),
        }

    def cycles(self) -> list[str]:
        return [
            r["cycle_id"]
            for r in self.conn.execute(
                "SELECT DISTINCT cycle_id FROM transfer_packages ORDER BY cycle_id"
            ).fetchall()
        ]

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["payload"] = json.loads(data["payload"])
        return data

    # -- suggestions ------------------------------------------------------------
    def save_suggestion(
        self,
        cycle_id: str,
        source_node: str,
        language: str,
        status: str,
        payload: dict[str, Any],
    ) -> SaveOutcome:
        digest = content_hash(payload)
        latest = self.conn.execute(
            "SELECT revision, content_hash FROM transfer_suggestions WHERE cycle_id=? AND source_node=? "
            "AND language=? AND is_latest=1",
            (cycle_id, source_node, language),
        ).fetchone()
        if latest is not None and latest["content_hash"] == digest:
            return SaveOutcome("unchanged", int(latest["revision"]), digest)
        revision = 1 if latest is None else int(latest["revision"]) + 1
        with self.conn:
            self.conn.execute(
                "UPDATE transfer_suggestions SET is_latest=0 WHERE cycle_id=? AND source_node=? "
                "AND language=?",
                (cycle_id, source_node, language),
            )
            self.conn.execute(
                "INSERT INTO transfer_suggestions (cycle_id, source_node, language, revision, is_latest, status, "
                "content_hash, created_at, payload) VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)",
                (
                    cycle_id,
                    source_node,
                    language,
                    revision,
                    status,
                    digest,
                    _now(),
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                ),
            )
        return SaveOutcome(
            "inserted" if latest is None else "updated", revision, digest
        )

    def latest_suggestions(self, cycle_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM transfer_suggestions WHERE cycle_id=? AND is_latest=1 ORDER BY source_node, language",
            (cycle_id,),
        ).fetchall()
        return [self._row(r) for r in rows]
