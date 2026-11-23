"""Phase 14 ACL to the Phase 13 results: AI-text jobs and the id-list prompts."""

import json
from pathlib import Path

import pytest
import yaml

from rag_core.rfp.infrastructure.prompts_yaml import load_rfp_prompts, prompt_set
from rag_core.shared_kernel.errors import InvariantError
from rag_core.tuning.domain.required_ids import id_checklist
from rag_core.tuning.infrastructure.ids_acl import IdJob, jobs_from_phase13, load_jobs, newest_results, render_job
from tests.fixtures.tuning.samples import IDS_DIR, RFP_DIR

pytestmark = [pytest.mark.tuning, pytest.mark.rfp]

PAYLOAD = {
    "rfp": {"rfps": {"AR-RFP-1403-07": {
        "fa": {"facts": ["f1", "f2"], "items": ["AR-RFP-1403-07", "AR-ISS-024", "AR-ISS-024/WEB"], "gaps": []},
        "en": {"facts": ["f1"], "items": ["AR-RFP-1403-07", "AR-ISS-024"], "gaps": []}}}},
    "feedback": {"PRP-02": {"fa": {"facts": ["g1"], "items": ["PRP-02"], "gaps": ["AR-ISS-024/WEB"]},
                            "en": {"facts": ["g1"], "items": ["PRP-02"], "gaps": []}},
                 "PRP-01": {"en": {"facts": ["x"], "items": ["PRP-01"], "gaps": []}}},
    "proposals": {"evaluation": {"winner": "PRP-01", "runner_up": "PRP-02"}},
}


def listed() -> dict:
    return {t: prompt_set(yaml.safe_load((IDS_DIR / f"{t}.yaml").read_text(encoding="utf-8")), t)
            for t in ("rfp_summary", "feedback")}


def baseline() -> dict:
    p = load_rfp_prompts(RFP_DIR)
    return {"rfp_summary": p.rfp_summary, "feedback": p.feedback}


def test_jobs_mirror_the_phase13_live_step() -> None:
    jobs = jobs_from_phase13(PAYLOAD)
    assert [j.label for j in jobs] == ["rfp_summary AR-RFP-1403-07 fa", "feedback PRP-02 fa",
                                       "rfp_summary AR-RFP-1403-07 en", "feedback PRP-02 en"]
    assert jobs[0].gaps == ("AR-ISS-024", "AR-ISS-024/WEB") and jobs[0].required == jobs[0].items
    assert jobs[1].required == ("PRP-02", "AR-ISS-024/WEB") and jobs[1].reply_key == "feedback"
    assert jobs[0].reply_key == "summary" and jobs[0].facts == ("f1", "f2")


def test_jobs_without_a_runner_up_or_facts() -> None:
    data = {**PAYLOAD, "proposals": {"evaluation": {"runner_up": None}}}
    assert [j.task for j in jobs_from_phase13(data)] == ["rfp_summary", "rfp_summary"]
    assert jobs_from_phase13({}) == [] and jobs_from_phase13(PAYLOAD, ["en"])[0].language == "en"


def test_bad_payload() -> None:
    with pytest.raises(InvariantError, match="mapping"):
        jobs_from_phase13({"rfp": {"rfps": ["x"]}})


def test_newest_results_and_load(tmp_path: Path) -> None:
    assert newest_results(tmp_path) is None and load_jobs(tmp_path) == ([], None)
    (tmp_path / "rfp-check-20261101T000000Z.json").write_text("{}", encoding="utf-8")
    (tmp_path / "rfp-check-20261123T194948Z.json").write_text(json.dumps(PAYLOAD), encoding="utf-8")
    jobs, path = load_jobs(tmp_path)
    assert path is not None and path.name == "rfp-check-20261123T194948Z.json" and len(jobs) == 4


def test_listed_prompts_load_and_need_facts() -> None:
    prompts = listed()
    assert prompts["rfp_summary"].prompt_id == "rfp-summary-ids" and prompts["feedback"].prompt_id == "rfp-feedback-ids"
    for p in prompts.values():
        for text in (p.user_en, p.user_fa):
            assert "{checklist}" in text and "{facts}" in text and text.index("{checklist}") < text.index("{facts}")


def test_render_listed_puts_the_checklist_in_the_prompt() -> None:
    job = jobs_from_phase13(PAYLOAD)[0]
    for variant in ("listed", "listed_retry"):
        system, user = render_job(job, variant, baseline(), listed())
        assert id_checklist(job.required) in user and "f1\nf2" in user and "{checklist}" not in user
        assert system


def test_render_baseline_uses_the_phase13_prompt() -> None:
    job = IdJob("feedback", "PRP-02", "en", ("g1",), ("PRP-02",), ("AR-ISS-024/WEB",))
    system, user = render_job(job, "baseline", baseline(), listed())
    assert "PRP-02, AR-ISS-024/WEB" in user and "{items}" not in user and "1. PRP-02" not in user


def test_render_unknown_variant() -> None:
    job = jobs_from_phase13(PAYLOAD)[0]
    with pytest.raises(InvariantError, match="unknown id variant"):
        render_job(job, "shout", baseline(), listed())
