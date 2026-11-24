"""SQLite store: latest package per (cycle, node), revisions and history."""

from dataclasses import replace
from pathlib import Path

import pytest

from rag_core.transfer.infrastructure.sqlite_store import SqliteTransferStore
from tests.fixtures.transfer.samples import (
    built,
    empty_team,
    hw_item,
    team_hw,
    team_win,
)

pytestmark = [pytest.mark.transfer, pytest.mark.transfer_pkg]


def test_first_save_inserts_revision_one(tmp_path: Path) -> None:
    with SqliteTransferStore(tmp_path / "db" / "t.sqlite") as store:
        out = store.save(built(team_hw(), "N-HW", 2))
        assert (out.action, out.revision) == ("inserted", 1)
        row = store.latest("1403-Q2", "N-HW-REP")
        assert row is not None and row["is_latest"] == 1
        assert row["payload"]["source_node"] == "N-HW-REP"
        assert row["status"] == "accepted" and row["items"] == 2


def test_same_content_is_unchanged(tmp_path: Path) -> None:
    with SqliteTransferStore(tmp_path / "t.sqlite") as store:
        store.save(built(team_hw(), "N-HW", 2))
        again = store.save(built(team_hw(), "N-HW", 2))
        assert (again.action, again.revision) == ("unchanged", 1)
        assert store.stats("1403-Q2") == {
            "rows": 1,
            "latest": 1,
            "max_revision": 1,
            "cycles": 1,
        }


def test_changed_content_adds_revision_and_keeps_history(tmp_path: Path) -> None:
    with SqliteTransferStore(tmp_path / "t.sqlite") as store:
        store.save(built(team_hw(), "N-HW", 2))
        changed = team_hw(replace(hw_item(), status="resolved"))
        out = store.save(built(changed, "N-HW", 2))
        assert (out.action, out.revision) == ("updated", 2)
        history = store.history("1403-Q2", "N-HW-REP")
        assert [(h["revision"], h["is_latest"]) for h in history] == [(1, 0), (2, 1)]
        assert store.latest("1403-Q2", "N-HW-REP")["revision"] == 2


def test_latest_all_orders_by_layer_then_node(tmp_path: Path) -> None:
    with SqliteTransferStore(tmp_path / "t.sqlite") as store:
        store.save(built(team_win(), "N-SW", 2))
        store.save(built(team_hw(), "N-HW", 2))
        store.save(built(empty_team(), "N-HW", 2))
        assert [r["source_node"] for r in store.latest_all("1403-Q2")] == [
            "N-HW-REP",
            "N-HW-SAL",
            "N-SW-WIN",
        ]
        assert store.latest_all("1403-Q3") == []


def test_reopen_keeps_data(tmp_path: Path) -> None:
    path = tmp_path / "t.sqlite"
    with SqliteTransferStore(path) as store:
        store.save(built(team_hw(), "N-HW", 2))
    with SqliteTransferStore(path) as store:
        assert store.cycles() == ["1403-Q2"]
        assert store.save(built(team_hw(), "N-HW", 2)).action == "unchanged"


def test_missing_latest_is_none(tmp_path: Path) -> None:
    with SqliteTransferStore(tmp_path / "t.sqlite") as store:
        assert store.latest("1403-Q2", "N-NOPE") is None
        assert store.stats() == {"rows": 0, "latest": 0, "max_revision": 0, "cycles": 0}


def test_suggestions_are_versioned(tmp_path: Path) -> None:
    with SqliteTransferStore(tmp_path / "t.sqlite") as store:
        a = store.save_suggestion(
            "1403-Q2", "N-CEO", "fa", "accepted", {"summary": "الف"}
        )
        b = store.save_suggestion(
            "1403-Q2", "N-CEO", "fa", "accepted", {"summary": "الف"}
        )
        c = store.save_suggestion(
            "1403-Q2", "N-CEO", "fa", "rejected", {"summary": "ب"}
        )
        assert [a.action, b.action, c.action] == ["inserted", "unchanged", "updated"]
        rows = store.latest_suggestions("1403-Q2")
        assert (
            len(rows) == 1
            and rows[0]["revision"] == 2
            and rows[0]["payload"]["summary"] == "ب"
        )
