"""Phase 14 strict judge prompts (config/prompts/judge_strict) with the ${checklist} variable."""

from pathlib import Path

import pytest

from rag_core.judging.domain.cases import Expectation, JudgeCase
from rag_core.judging.domain.rubric import OutputKind
from rag_core.judging.infrastructure.calibration_json import load_calibration
from rag_core.judging.infrastructure.prompt_yaml import load_judge_prompts, load_rubric
from rag_core.shared_kernel.errors import InvariantError
from rag_core.tuning.infrastructure.judging_acl import (
    ChecklistJudgePrompt,
    checklist_lines,
    expanded_calibration,
    load_strict_prompts,
    strict_prompt_from_dict,
)
from tests.fixtures.tuning.samples import (
    CALIBRATION,
    JUDGE_DIR,
    RUBRIC,
    STRICT_DIR,
    shipped_items,
)

pytestmark = [pytest.mark.tuning, pytest.mark.judging]


def test_strict_prompts_cover_every_kind() -> None:
    prompts = load_strict_prompts(STRICT_DIR)
    assert set(prompts) == {"qa_answer", "qa_refusal", "ike_summary"}
    assert (
        prompts["qa_answer"].label == "judge.qa.strict@2.0.0"
        and prompts["qa_answer"] is prompts["qa_refusal"]
    )
    assert prompts["ike_summary"].label == "judge.summary.strict@2.0.0"
    assert all(isinstance(p, ChecklistJudgePrompt) for p in prompts.values())


def test_strict_dir_does_not_clash_with_the_baseline_dir() -> None:
    base = load_judge_prompts(JUDGE_DIR)
    strict = load_strict_prompts(STRICT_DIR)
    assert {p.prompt_id for p in base.values()}.isdisjoint(
        {p.prompt_id for p in strict.values()}
    )


def test_answer_checklist_lists_every_fact_group() -> None:
    case = JudgeCase(
        "c",
        OutputKind.QA_ANSWER,
        "en",
        "q",
        "out",
        expectation=Expectation(facts=(("30", "thirty"), ("4",))),
    )
    lines = checklist_lines(case)
    assert (
        lines[0] == "1. The output states: 30 | thirty"
        and lines[1] == "2. The output states: 4"
    )
    assert lines[-1] == f"{len(lines)}. The output is written in English"


def test_refusal_checklist() -> None:
    out = JudgeCase(
        "c",
        OutputKind.QA_REFUSAL,
        "fa",
        "q",
        "o",
        expectation=Expectation(status="out_of_scope", escalation="N-CEO"),
    )
    assert any("escalation to N-CEO" in line for line in checklist_lines(out))
    assert checklist_lines(out)[-1].endswith("Persian")
    nf = JudgeCase(
        "c",
        OutputKind.QA_REFUSAL,
        "en",
        "q",
        "o",
        expectation=Expectation(status="not_found"),
    )
    assert any("what is missing" in line for line in checklist_lines(nf))


def test_summary_checklist_lists_the_ids() -> None:
    case = JudgeCase(
        "c",
        OutputKind.IKE_SUMMARY,
        "en",
        "t",
        "o",
        expectation=Expectation(
            status="summary",
            items=("AR-ISS-024/WEB",),
            item_leads=(("AR-ISS-024/HW", ("Saeed Akbari",)),),
            gaps=("AR-ISS-024/WEB",),
        ),
    )
    lines = checklist_lines(case)
    assert "1. The summary writes the id AR-ISS-024/WEB" in lines
    assert "2. The summary writes the id AR-ISS-024/HW" in lines
    assert sum("writes the id" in line for line in lines) == 2
    assert any("Saeed Akbari" in line for line in lines)


def test_every_calibration_case_renders_with_a_checklist() -> None:
    rubric = load_rubric(RUBRIC)
    prompts = load_strict_prompts(STRICT_DIR)
    cases = expanded_calibration(load_calibration(CALIBRATION), shipped_items())
    for case in cases:
        system, user = prompts[case.kind.value].render(case, rubric)
        assert "${" not in system + user, case.case_id
        assert (
            "CHECKLIST" in user and "1. " in user and case.output.strip()[:20] in user
        ), case.case_id


def test_strict_prompt_requires_the_checklist_variable() -> None:
    data = {
        "id": "x",
        "version": "1",
        "kinds": ["qa_answer"],
        "system": "${criteria} ${reply_format}",
        "user": "${output} ${sources}",
    }
    with pytest.raises(InvariantError, match="checklist"):
        strict_prompt_from_dict(data)
    ok = strict_prompt_from_dict({**data, "user": "${output} ${sources} ${checklist}"})
    assert isinstance(ok, ChecklistJudgePrompt)


def test_missing_kind_and_duplicate_kind(tmp_path: Path) -> None:
    body = (
        "type: prompt\nid: {id}\nversion: '1'\nkinds: [{kinds}]\nsystem: '${{criteria}} ${{reply_format}}'\n"
        "user: '${{output}} ${{sources}} ${{checklist}}'\n"
    )
    (tmp_path / "a.yaml").write_text(
        body.format(id="a", kinds="qa_answer"), encoding="utf-8"
    )
    with pytest.raises(InvariantError, match="no strict judge prompt"):
        load_strict_prompts(tmp_path)
    (tmp_path / "b.yaml").write_text(
        body.format(id="b", kinds="qa_answer, qa_refusal, ike_summary"),
        encoding="utf-8",
    )
    with pytest.raises(InvariantError, match="two strict prompts"):
        load_strict_prompts(tmp_path)
