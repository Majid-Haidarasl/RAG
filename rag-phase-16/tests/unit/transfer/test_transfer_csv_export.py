"""CSV export of the latest packages and the read-back check."""

import csv
from io import StringIO
from pathlib import Path

import pytest

from rag_core.transfer.infrastructure.csv_export import (
    INDEX_COLUMNS,
    INDEX_FILE,
    citation_from_text,
    export_latest,
    round_trip_problems,
)
from rag_core.transfer.infrastructure.csv_format import package_from_csv
from rag_core.transfer.infrastructure.sqlite_store import SqliteTransferStore
from tests.fixtures.transfer.samples import built, team_hw, team_win

pytestmark = [pytest.mark.transfer, pytest.mark.transfer_pkg]


def rows(tmp_path: Path) -> list[dict]:
    with SqliteTransferStore(tmp_path / "t.sqlite") as store:
        store.save(built(team_hw(), "N-HW", 2))
        store.save(built(team_win(), "N-SW", 2))
        return store.latest_all("1403-Q2")


def test_export_writes_one_file_per_package_and_index(tmp_path: Path) -> None:
    data = rows(tmp_path)
    files = export_latest(data, tmp_path / "out", "1403-Q2")
    assert sorted(p.name for p in files) == ["N-HW-REP.csv", "N-SW-WIN.csv", INDEX_FILE]
    index = list(
        csv.reader(
            StringIO(
                (tmp_path / "out" / "1403-Q2" / INDEX_FILE).read_text(encoding="utf-8")
            )
        )
    )
    assert tuple(index[0]) == INDEX_COLUMNS
    assert [r[1] for r in index[1:]] == ["N-HW-REP", "N-SW-WIN"]


def test_exported_package_keeps_persian_text(tmp_path: Path) -> None:
    export_latest(rows(tmp_path), tmp_path / "out", "1403-Q2")
    pkg = package_from_csv(
        (tmp_path / "out" / "1403-Q2" / "N-HW-REP.csv").read_text(encoding="utf-8")
    )
    assert "سعید اکبری" in pkg.fields["summary_fa"]
    assert pkg.status.value == "accepted"
    assert str(pkg.target_node) == "N-HW"


def test_round_trip_is_clean_and_stale_files_are_removed(tmp_path: Path) -> None:
    data = rows(tmp_path)
    folder = tmp_path / "out" / "1403-Q2"
    folder.mkdir(parents=True)
    (folder / "N-OLD.csv").write_text("key,value\n", encoding="utf-8")
    export_latest(data, tmp_path / "out", "1403-Q2")
    assert not (folder / "N-OLD.csv").exists()
    assert round_trip_problems(data, tmp_path / "out", "1403-Q2") == []


def test_round_trip_reports_missing_files(tmp_path: Path) -> None:
    data = rows(tmp_path)
    export_latest(data, tmp_path / "out", "1403-Q2")
    (tmp_path / "out" / "1403-Q2" / "N-SW-WIN.csv").unlink()
    assert round_trip_problems(data, tmp_path / "out", "1403-Q2") == [
        "N-SW-WIN: file missing"
    ]
    assert str(citation_from_text("AR-HW-012@1.2")) == "AR-HW-012@1.2"
