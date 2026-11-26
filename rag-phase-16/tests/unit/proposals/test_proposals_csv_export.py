"""Phase 13 CSV export of the RFP tables and the read-back check."""

import pytest

from rag_core.proposals.infrastructure.csv_export import (
    TABLES,
    cell,
    export_tables,
    read_table,
    round_trip_problems,
)

pytestmark = [pytest.mark.proposals]

TABLES_IN = {
    "rfp_requirements": [
        {
            "requirement_id": "REQ-NEED",
            "rfp_id": "AR-RFP-1403-07",
            "section": "need",
            "mandatory": True,
            "statement_fa": "نیاز به ماژول گزارش",
            "evidence": ["AR-RFP-025"],
        }
    ],
    "proposals": [
        {
            "proposal_id": "PRP-A",
            "price_mtoman": 285,
            "sections": ["architecture", "pricing"],
        }
    ],
    "evaluation": [
        {
            "row_id": "PRP-A/CRT-TECH",
            "weight": "0.6",
            "score": "82",
            "contribution": "49.2",
        }
    ],
    "feedback": [
        {"row_id": "PRP-B/fa", "language": "fa", "text": "نتیجه:\nامتیاز وزنی 75.2"}
    ],
    "knowledge_links": [
        {"link_id": "LNK-LIBRARY", "node": "N-LIB", "executor": "", "valid": True}
    ],
}


def test_export_and_read_back(tmp_path) -> None:
    files = export_tables(TABLES_IN, tmp_path, "AR-RFP-1403-07")
    assert [f.name for f in files] == [f"{n}.csv" for n in TABLES]
    assert (
        files[0].read_bytes().startswith(b"\xef\xbb\xbf")
    )  # BOM for spreadsheet programs
    assert round_trip_problems(TABLES_IN, tmp_path, "AR-RFP-1403-07") == []
    rows = read_table(tmp_path, "AR-RFP-1403-07", "feedback")
    assert rows[0]["text"] == "نتیجه:\nامتیاز وزنی 75.2"


def test_round_trip_detects_a_changed_cell(tmp_path) -> None:
    export_tables(TABLES_IN, tmp_path, "AR-RFP-1403-07")
    changed = {
        **TABLES_IN,
        "evaluation": [{**TABLES_IN["evaluation"][0], "contribution": "49.3"}],
    }
    assert round_trip_problems(changed, tmp_path, "AR-RFP-1403-07") == [
        "evaluation:PRP-A/CRT-TECH:contribution"
    ]


def test_missing_folder_is_reported(tmp_path) -> None:
    problems = round_trip_problems(TABLES_IN, tmp_path, "AR-RFP-1403-99")
    assert len(problems) == len(TABLES) and problems[0].startswith("rfp_requirements: ")


def test_cell_format() -> None:
    assert (cell(None), cell(True), cell(["a", "b"]), cell(3)) == (
        "",
        "true",
        "a;b",
        "3",
    )
