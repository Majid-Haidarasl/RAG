"""Phase 14 required ids: checklist, missing ids, retry note and run summaries."""

import pytest

from rag_core.tuning.domain.required_ids import (
    IdRun,
    id_checklist,
    mention_count,
    mentioned,
    missing_ids,
    required_ids,
    retry_note,
    summarize_id_runs,
)

pytestmark = [pytest.mark.tuning, pytest.mark.eval_metrics]

IDS = ("AR-RFP-1403-07", "AR-ISS-024", "AR-ISS-024/WEB")


def test_required_ids_dedupe_and_strip() -> None:
    assert required_ids(
        [" AR-ISS-024", "AR-ISS-024/WEB", ""], ["AR-ISS-024/WEB", "PRP-02"]
    ) == ("AR-ISS-024", "AR-ISS-024/WEB", "PRP-02")


def test_mentioned_is_case_and_digit_insensitive() -> None:
    assert mentioned("see ar-iss-024/web", "AR-ISS-024/WEB")
    assert mentioned("AR-RFP-۱۴۰۳-۰۷ آمده", "AR-RFP-1403-07")
    assert not mentioned("AR-ISS-024 only", "AR-ISS-024/WEB")


def test_missing_and_count() -> None:
    text = "AR-RFP-1403-07 covers AR-ISS-024."
    assert missing_ids(text, IDS) == ("AR-ISS-024/WEB",)
    assert mention_count(text, IDS) == (2, 3) and mention_count("", ()) == (0, 0)


def test_checklist_lines() -> None:
    assert id_checklist(IDS) == "1. AR-RFP-1403-07\n2. AR-ISS-024\n3. AR-ISS-024/WEB"
    assert id_checklist(()) == ""


def test_retry_note_names_the_missing_ids() -> None:
    fa = retry_note(("AR-ISS-024/WEB",), "fa")
    en = retry_note(("AR-ISS-024/WEB", "PRP-02"), "en")
    assert "AR-ISS-024/WEB" in fa and "JSON" in fa and "شناسه" in fa
    assert "AR-ISS-024/WEB, PRP-02" in en and "Do not add" in en


def run(
    variant: str,
    mentioned_: int,
    expected: int = 3,
    accepted: bool = True,
    **kw: object,
) -> IdRun:
    return IdRun(
        "rfp_summary",
        "AR-RFP-1403-07",
        "en",
        variant,
        mentioned_,
        expected,
        True,
        (),
        accepted,
        **kw,
    )


def test_all_ids_property() -> None:
    assert run("listed", 3).all_ids and not run("listed", 2).all_ids
    assert not IdRun("t", "s", "en", "listed", 0, 0, True, (), False).all_ids


def test_run_to_dict() -> None:
    d = run("listed_retry", 3, attempts=2, seconds=1.23456, rule_total=19).to_dict()
    assert (
        d["mentioned"] == "3/3"
        and d["all_ids"]
        and d["attempts"] == 2
        and d["seconds"] == 1.235
    )
    assert d["rule_total"] == 19 and d["invented"] == []


def test_summarize_id_runs() -> None:
    rows = [
        run("baseline", 2, accepted=False),
        run("baseline", 1, accepted=False),
        run("listed_retry", 3, attempts=2, seconds=2.0),
        run("listed_retry", 3, seconds=1.0),
        IdRun(
            "feedback",
            "PRP-02",
            "fa",
            "listed",
            0,
            2,
            False,
            ("AR-X-1",),
            False,
            error="timeout",
        ),
    ]
    s = summarize_id_runs(rows)
    assert s["baseline"]["mentioned"] == "3/6" and s["baseline"]["mention_rate"] == 0.5
    assert s["baseline"]["accept_rate"] == 0.0 and s["baseline"]["all_ids"] == 0
    assert s["listed_retry"]["all_ids"] == 2 and s["listed_retry"]["retries"] == 1
    assert (
        s["listed_retry"]["seconds_avg"] == 1.5
        and s["listed_retry"]["accept_rate"] == 1.0
    )
    assert (
        s["listed"]["errors"] == 1
        and s["listed"]["invented_ids"] == 1
        and s["listed"]["grounded"] == 0
    )
