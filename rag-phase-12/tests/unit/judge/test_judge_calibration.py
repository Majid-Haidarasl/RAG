"""Phase 10 calibration set and case model."""

import json
from pathlib import Path

import pytest

from rag_core.judging.domain.cases import JudgeCase
from rag_core.judging.domain.rubric import OutputKind
from rag_core.judging.domain.text import (
    arabic_share,
    bracket_refs,
    groups_found,
    language_matches,
    sentences,
)
from rag_core.judging.infrastructure.calibration_json import (
    case_from_dict,
    load_calibration,
    load_parser_cases,
)
from rag_core.shared_kernel.errors import InvariantError

pytestmark = [pytest.mark.judging, pytest.mark.judge]

ROOT = Path(__file__).resolve().parents[3]
CALIBRATION = ROOT / "data" / "judge" / "calibration-set.json"


def test_calibration_set_shape() -> None:
    cases = load_calibration(CALIBRATION)
    assert len(cases) == 14
    gold = [c.gold for c in cases]
    assert gold.count("accept") == 8 and gold.count("reject") == 6
    assert {c.language for c in cases} == {"fa", "en"}
    assert {c.kind for c in cases} == {OutputKind.QA_ANSWER, OutputKind.QA_REFUSAL}
    assert [c.case_id for c in cases if "rule_blind_spot" in c.tags] == ["CAL-N06"]
    assert all(c.origin == "calibration" for c in cases)


def test_calibration_answers_cite_their_own_sources() -> None:
    for case in load_calibration(CALIBRATION):
        if case.kind is OutputKind.QA_ANSWER and case.gold == "accept":
            docs = {b.document_id for b in case.sources}
            assert (
                docs and {r.document_id for r in bracket_refs(case.output)} <= docs
            ), case.case_id
            assert groups_found(case.output, case.expectation.facts)[0] == len(
                case.expectation.facts
            ), case.case_id


def test_calibration_loader_requires_gold_and_unique_ids(tmp_path: Path) -> None:
    item = {
        "id": "X",
        "kind": "qa_answer",
        "language": "en",
        "output": "o",
        "gold": "accept",
    }
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"cases": [item, item]}), encoding="utf-8")
    with pytest.raises(InvariantError, match="duplicate"):
        load_calibration(path)
    path.write_text(json.dumps({"cases": [{**item, "gold": ""}]}), encoding="utf-8")
    with pytest.raises(InvariantError, match="gold"):
        load_calibration(path)


def test_parser_case_loader_requires_fields(tmp_path: Path) -> None:
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"cases": [{"id": "P", "raw": "x"}]}), encoding="utf-8")
    with pytest.raises(InvariantError):
        load_parser_cases(path)


def test_case_validation_and_mutation() -> None:
    case = case_from_dict(
        {
            "id": "A",
            "kind": "qa_answer",
            "language": "fa",
            "output": "o",
            "sources": [
                {
                    "label": "AR-SW-022 §4",
                    "text": "t",
                    "document_id": "AR-SW-022",
                    "order": 4,
                }
            ],
            "expected": {"facts": [["30", "سی"]]},
        }
    )
    assert (
        case.sources[0].order == 4
        and case.expectation.facts == (("30", "سی"),)
        and case.gold == ""
    )
    neg = case.mutated("x", "new")
    assert (
        neg.case_id == "A~x"
        and neg.gold == "reject"
        and neg.is_negative
        and neg.output == "new"
    )
    assert not case.is_negative
    with pytest.raises(InvariantError):
        JudgeCase("", OutputKind.QA_ANSWER, "fa", "t", "o")
    with pytest.raises(InvariantError):
        JudgeCase("B", OutputKind.QA_ANSWER, "de", "t", "o")
    with pytest.raises(InvariantError):
        JudgeCase("B", OutputKind.QA_ANSWER, "fa", "t", "o", gold="maybe")
    assert JudgeCase("C", "ike_summary", "en", "t", "o").kind is OutputKind.IKE_SUMMARY  # type: ignore[arg-type]


def test_text_helpers() -> None:
    refs = bracket_refs("a [AR-SW-022 §۴; AR-HR-005 §12/en] b [AR-SW-022 §4] c [note]")
    assert [r.label for r in refs] == ["AR-SW-022 §4", "AR-HR-005 §12/en"]
    assert groups_found("پاسخ ظرف ۳۰ دقیقه", (("30", "سی"), ("4", "چهار"))) == (1, 2)
    assert arabic_share("short") is None
    assert language_matches("این یک پاسخ فارسی است [AR-SW-022 §4]", "fa") is True
    assert language_matches("This is an English answer [AR-SW-022 §4]", "fa") is False
    assert sentences("First sentence. [AR-SW-022 §4]\nSecond one!") == [
        "First sentence. [AR-SW-022 §4]",
        "Second one!",
    ]
