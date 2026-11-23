"""Phase 10 config files: config/judge.yaml, rubric.yaml and the judge prompts."""

from pathlib import Path

import pytest

from rag_core.judging.domain.cases import SourceBlock
from rag_core.judging.domain.prompts import JudgePromptSet, render_sources
from rag_core.judging.domain.rubric import OutputKind, default_rubric
from rag_core.judging.infrastructure.config import judge_settings_from_dict, load_judge_settings
from rag_core.judging.infrastructure.prompt_yaml import load_judge_prompts, load_rubric, prompt_from_dict
from rag_core.shared_kernel.errors import InvariantError
from tests.fixtures.judge.samples import OUT_OF_SCOPE_FA, qa_en, qa_fa, refusal_case

pytestmark = [pytest.mark.judging, pytest.mark.judge]

ROOT = Path(__file__).resolve().parents[3]
PROMPT_DIR = ROOT / "config" / "prompts" / "judge"


def test_judge_yaml_loads_with_low_temperature_json_and_gpu_friendly_context() -> None:
    s = load_judge_settings(ROOT / "config" / "judge.yaml")
    assert s.config_version == "0.10.0"
    assert s.model.model == "qwen3:8b" and s.model.think is False and s.model.format == "json"
    assert s.model.options["temperature"] == 0.0 and s.model.options["num_ctx"] <= 8192
    assert s.run.retries == 1 and s.run.max_live_cases <= 60
    assert s.files.prompt_dir == "config/prompts/judge" and s.rules.max_answer_chars == 1200
    for rel in (s.files.rubric, s.files.prompt_dir, s.files.calibration, s.files.parser_cases):
        assert (ROOT / rel).exists(), rel


def test_judge_settings_reject_unknown_keys() -> None:
    with pytest.raises(InvariantError):
        judge_settings_from_dict({"modle": {}})
    with pytest.raises(InvariantError):
        judge_settings_from_dict({"run": {"retry": 2}})
    with pytest.raises(InvariantError):
        judge_settings_from_dict({"run": [1, 2]})
    assert judge_settings_from_dict({}).model.model == "qwen3:8b"


def test_rubric_yaml_matches_the_default_rubric() -> None:
    from_yaml = load_rubric(PROMPT_DIR / "rubric.yaml")
    default = default_rubric()
    assert from_yaml.label == default.label
    assert from_yaml.maximums == default.maximums and from_yaml.minimums == default.minimums
    assert (from_yaml.out_of, from_yaml.accept_total) == (20, 18)
    for c in from_yaml.criteria:
        assert set(default.criterion(c.key).aliases) <= set(c.aliases)
        for kind in OutputKind:
            assert c.guidance_for(kind.value), (c.key, kind)


def test_every_output_kind_has_exactly_one_prompt() -> None:
    prompts = load_judge_prompts(PROMPT_DIR)
    assert set(prompts) == {k.value for k in OutputKind}
    assert prompts["qa_answer"] is prompts["qa_refusal"]
    assert prompts["ike_summary"].label == "judge.summary@1.0.0"


@pytest.mark.parametrize("case", [qa_fa(), qa_en(), refusal_case(OUT_OF_SCOPE_FA, "out_of_scope", escalation="N-CEO")],
                         ids=["answer-fa", "answer-en", "refusal"])
def test_qa_prompt_renders_without_leftover_placeholders(case) -> None:  # noqa: ANN001
    rubric = load_rubric(PROMPT_DIR / "rubric.yaml")
    system, user = load_judge_prompts(PROMPT_DIR)[case.kind.value].render(case, rubric)
    assert "${" not in system + user
    assert case.output in user and case.task in user
    assert '"grounding": <0-5>' in system and "maximum 20" in system and "below 18" in system
    if case.kind is OutputKind.QA_REFUSAL:
        assert "escalation to N-CEO" in user and "(no sources were retrieved)" in user
        assert "suggested escalation: N-CEO" in user
    else:
        assert "Reference key facts" in user


def test_prompt_validation() -> None:
    base = {"id": "x", "version": "1", "kinds": ["qa_answer"], "system": "${criteria} ${reply_format}",
            "user": "${sources} ${output}"}
    assert isinstance(prompt_from_dict(base), JudgePromptSet)
    with pytest.raises(InvariantError):
        prompt_from_dict({**base, "kinds": ["poem"]})
    with pytest.raises(InvariantError):
        prompt_from_dict({**base, "user": "${output} only"})
    with pytest.raises(InvariantError):
        prompt_from_dict({**base, "system": "no rubric here"})
    bad = prompt_from_dict({**base, "user": "${sources} ${output} ${unknown_var}"})
    with pytest.raises(InvariantError):
        bad.render(qa_en(), default_rubric())


def test_prompt_dir_must_cover_every_kind(tmp_path: Path) -> None:
    (tmp_path / "only.yaml").write_text(
        "id: only\ntype: prompt\nversion: '1'\nkinds: [qa_answer]\nsystem: '${criteria} ${reply_format}'\n"
        "user: '${sources} ${output}'\n", encoding="utf-8")
    with pytest.raises(InvariantError, match="no judge prompt"):
        load_judge_prompts(tmp_path)


def test_render_sources_respects_the_budget() -> None:
    blocks = tuple(SourceBlock(f"AR-SW-0{i} §1", "x" * 500, f"AR-SW-0{i}", 1) for i in range(10, 20))
    text = render_sources(blocks, 1200)
    assert text.startswith("[AR-SW-010 §1]") and "more source block(s) omitted" in text
    assert len(text) < 2000
    assert render_sources((), 100) == "(no sources were retrieved)"
