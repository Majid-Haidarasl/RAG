"""Phase 12 CSV export of the tracking tables and the read-back check."""

from pathlib import Path

import pytest

from rag_core.projects.infrastructure.csv_export import (
    TABLES,
    export_tables,
    read_table,
    round_trip_problems,
)

pytestmark = [pytest.mark.projects]

TABLES_DATA = {
    "projects": [
        {
            "project_id": "PRJ-AZP-118",
            "name_en": "Azarpakhsh warehouse system",
            "name_fa": "سامانه انبار آذرپخش",
            "owner_node": "N-CEO",
            "status": "at_risk",
            "health": "at_risk",
            "progress_percent": 62,
            "remaining_mtoman": 1240,
            "contract_value_mtoman": None,
            "issues": 4,
            "open_issues": 3,
            "blocked_subissues": 2,
        }
    ],
    "records": [
        {
            "record_id": "CHL-LOST-CONDITIONS",
            "kind": "challenge",
            "state": "open",
            "project": "",
            "title_en": 'Conditions lost, "quoted"',
            "title_fa": "حذف شرط‌ها",
            "issues": [],
            "nodes": ["N-CEO", "N-SW"],
            "evidence": ["AR-TRN-026"],
            "conditions": "line one\nline two",
        }
    ],
    "gaps": [],
    "priorities": [
        {
            "rank": 1,
            "issue_id": "AR-ISS-024",
            "score": 80.75,
            "key": True,
            "top_factors": ["urgency", "risk"],
            "title_en": "Delay",
            "title_fa": "تأخیر",
        }
    ],
}


def test_export_writes_four_files_and_reads_back(tmp_path: Path) -> None:
    files = export_tables(TABLES_DATA, tmp_path, "1403-Q2")
    assert [f.name for f in files] == [f"{name}.csv" for name in TABLES]
    assert round_trip_problems(TABLES_DATA, tmp_path, "1403-Q2") == []


def test_cells_are_plain_text(tmp_path: Path) -> None:
    export_tables(TABLES_DATA, tmp_path, "1403-Q2")
    rec = read_table(tmp_path, "1403-Q2", "records")[0]
    assert (
        rec["nodes"] == "N-CEO;N-SW"
        and rec["issues"] == ""
        and rec["conditions"] == "line one\nline two"
    )
    pri = read_table(tmp_path, "1403-Q2", "priorities")[0]
    assert (pri["score"], pri["key"], pri["top_factors"]) == (
        "80.75",
        "true",
        "urgency;risk",
    )
    assert read_table(tmp_path, "1403-Q2", "projects")[0]["contract_value_mtoman"] == ""


def test_persian_text_survives(tmp_path: Path) -> None:
    export_tables(TABLES_DATA, tmp_path, "1403-Q2")
    assert (
        read_table(tmp_path, "1403-Q2", "projects")[0]["name_fa"]
        == "سامانه انبار آذرپخش"
    )
    assert (
        (tmp_path / "1403-Q2" / "gaps.csv")
        .read_text(encoding="utf-8-sig")
        .startswith("gap_id,rule,kind")
    )


def test_changed_file_is_a_round_trip_problem(tmp_path: Path) -> None:
    export_tables(TABLES_DATA, tmp_path, "1403-Q2")
    changed = {
        **TABLES_DATA,
        "priorities": [{**TABLES_DATA["priorities"][0], "score": 81.0}],
    }
    assert round_trip_problems(changed, tmp_path, "1403-Q2") == [
        "priorities:AR-ISS-024:score"
    ]
    more = {**TABLES_DATA, "gaps": [{"gap_id": "RG:RES-PHOTO-TRIAGE"}]}
    assert round_trip_problems(more, tmp_path, "1403-Q2") == [
        "gaps: 0 rows read, 1 written"
    ]
