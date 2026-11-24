"""Phase 10 anti-corruption layers: Phase 8 answers and Phase 9 summaries → judge cases."""

import json
from pathlib import Path

import pytest

from rag_core.ike.application.services import IkeService
from rag_core.ike.domain.summary import digest, facts_lines
from rag_core.judging.domain.rubric import OutputKind
from rag_core.judging.infrastructure.ike_acl import summary_case, summary_expectation
from rag_core.judging.infrastructure.qa_acl import (
    answer_sources,
    chunk_texts,
    phase8_cases,
    samples_by_id,
)
from rag_core.judging.infrastructure.results_files import latest_result, read_json
from tests.fixtures.ike.samples import NAMES, sample_issue, sample_referrals
from tests.fixtures.rag.fakes import rec, sample_records

pytestmark = [pytest.mark.judging, pytest.mark.judge]

ROOT = Path(__file__).resolve().parents[3]
SAMPLES = samples_by_id(ROOT / "data" / "rag" / "sample-questions.json")


def _answer(**changes: object) -> dict:
    base: dict = {
        "id": "Q01",
        "node": "N-SW-SUP",
        "language": "fa",
        "question": "زمان پاسخ اولویت ۱؟",
        "status": "answered",
        "expected_status": "answered",
        "text": "پاسخ ظرف ۳۰ دقیقه [AR-SW-022 §3].",
        "used_chunks": [
            {"document_id": "AR-HR-005", "language": "fa", "order": 1},
            {"document_id": "AR-SW-022", "language": "fa", "order": 3},
            {"document_id": "AR-SW-022", "language": "en", "order": 3},
        ],
        "citations": [
            {"label": "AR-SW-022 §3", "valid": True, "blocks": ["AR-SW-022 §3/fa"]}
        ],
    }
    base.update(changes)
    return base


def test_chunk_texts_keeps_active_records_only() -> None:
    texts = chunk_texts(sample_records())
    assert texts[("AR-HW-012", "en", 7)].startswith(
        "Level 1 repair is completed within four"
    )
    assert ("AR-SW-022", "fa", 3) in texts and ("AR-SW-022", "en", 3) in texts
    retired = chunk_texts(
        [rec("AR-X-001", 1, "old", status="retired", version_status="superseded")]
    )
    assert retired == {}


def test_answer_sources_put_cited_documents_first_and_mark_languages() -> None:
    blocks, missing = answer_sources(_answer(), chunk_texts(sample_records()))
    assert missing == 0
    assert [b.label for b in blocks] == [
        "AR-SW-022 §3/fa",
        "AR-SW-022 §3/en",
        "AR-HR-005 §1",
    ]
    assert (
        blocks[0].document_id == "AR-SW-022"
        and blocks[0].order == 3
        and blocks[0].language == "fa"
    )


def test_answer_sources_count_unknown_chunks() -> None:
    answer = _answer(
        used_chunks=[
            {"document_id": "AR-NOPE-001", "language": "fa", "order": 9},
            {"bad": 1},
        ]
    )
    blocks, missing = answer_sources(answer, chunk_texts(sample_records()))
    assert blocks == () and missing == 1


def test_phase8_cases_take_expectations_from_the_sample_questions() -> None:
    refusal = _answer(
        id="Q09",
        node="N-SW-WEB",
        status="out_of_scope",
        expected_status="out_of_scope",
        text="خارج از دامنه.",
        escalation={"target": "N-CEO"},
        used_chunks=[],
        citations=[],
    )
    cases, missing = phase8_cases(
        [_answer(), refusal], SAMPLES, chunk_texts(sample_records())
    )
    assert missing == 0
    q01, q09 = cases
    assert (
        q01.case_id == "P8-Q01"
        and q01.kind is OutputKind.QA_ANSWER
        and q01.origin == "phase8-live"
    )
    assert (
        q01.expectation.facts == (("30", "سی"), ("4", "چهار"))
        and q01.node == "N-SW-SUP"
    )
    assert (
        q09.kind is OutputKind.QA_REFUSAL and q09.refused and q09.escalation == "N-CEO"
    )
    assert (
        q09.expectation.escalation == "N-CEO"
        and q09.expectation.status == "out_of_scope"
    )


def test_phase8_case_without_sample_falls_back_safely() -> None:
    cases, _ = phase8_cases(
        [_answer(id="Q99", language="de", expected_status=None)], {}, {}
    )
    assert (
        cases[0].kind is OutputKind.QA_ANSWER
        and cases[0].language == "en"
        and cases[0].expectation.facts == ()
    )


def test_summary_expectation_reads_leads_items_and_gaps() -> None:
    issue = sample_issue()
    facts = facts_lines(
        digest(issue, IkeService().build(issue, sample_referrals())), NAMES
    )
    exp = summary_expectation(facts, NAMES)
    assert exp.status == "summary"
    assert exp.items == ("AR-ISS-050/HW", "AR-ISS-050/WIN", "AR-ISS-050/WEB")
    assert dict(exp.item_leads) == {
        "AR-ISS-050/HW": ("Saeed Akbari", "سعید اکبری"),
        "AR-ISS-050/WIN": ("Roozbeh Mohseni", "روزبه محسنی"),
    }
    assert set(exp.gaps) == {
        "AR-HW-015",
        "AR-SW-017",
        "AR-RFP-025",
        "gap:no-lead-executor",
    }


def test_summary_case_carries_the_facts_as_its_only_source() -> None:
    facts = [
        "sub-issue AR-ISS-050/HW: x | owner N-HW-REP | status s | lead none | collaborators none | knowledge none"
    ]
    case = summary_case(
        "S1", "en", "text", facts, NAMES, issue_id="AR-ISS-050", origin="ike-llm"
    )
    assert (
        case.kind is OutputKind.IKE_SUMMARY
        and case.status == "summary"
        and case.origin == "ike-llm"
    )
    assert (
        len(case.sources) == 1
        and case.sources[0].label == "FACTS"
        and case.sources[0].text == facts[0]
    )
    assert (
        case.expectation.items == ("AR-ISS-050/HW",)
        and case.expectation.item_leads == ()
    )
    assert "AR-ISS-050" in case.task and "English" in case.task


def test_latest_result_and_read_json(tmp_path: Path) -> None:
    assert latest_result(tmp_path / "missing", "*.json") is None
    assert latest_result(tmp_path, "rag-demo-*.json") is None
    for stamp in ("20260101T000000Z", "20261119T080000Z", "20260601T000000Z"):
        (tmp_path / f"rag-demo-{stamp}.json").write_text(
            json.dumps({"stamp": stamp}), encoding="utf-8"
        )
    newest = latest_result(tmp_path, "rag-demo-*.json")
    assert newest is not None and newest.name == "rag-demo-20261119T080000Z.json"
    assert read_json(newest) == {"stamp": "20261119T080000Z"}
    (tmp_path / "list.json").write_text("[1, 2]", encoding="utf-8")
    assert read_json(tmp_path / "list.json") == {}
