"""Phase 15 carry-overs of the Phase 14 findings: fact pre-check, invented-id guard, new defaults."""

from types import SimpleNamespace

import pytest

from rag_core.judging.domain.cases import Expectation, JudgeCase
from rag_core.judging.domain.results import JudgeResult
from rag_core.judging.domain.rubric import OutputKind
from rag_core.judging.domain.threshold import Decision, PolicyOutcome
from rag_core.judging.infrastructure.calibration_json import load_calibration
from rag_core.tuning.application.precheck import (
    PrecheckedJudge,
    PrecheckFinding,
    fact_precheck,
    precheck_summary,
    required_summary_ids,
)
from rag_core.tuning.application.services import Generated, IdVariantRunner, choose, id_candidates
from rag_core.tuning.domain.required_ids import LISTED_VARIANTS, RETRY_VARIANTS, IdVariant, guard_note, guard_rank
from rag_core.tuning.domain.variants import SelectionRule
from rag_core.tuning.infrastructure.config import JUDGE_VARIANTS, load_eval_settings
from rag_core.tuning.infrastructure.ids_acl import IdJob
from rag_core.tuning.infrastructure.judging_acl import derive_calibration
from tests.fixtures.tuning.samples import CALIBRATION, CONFIG, shipped_items

pytestmark = [pytest.mark.tuning, pytest.mark.carryover]

JOB = IdJob("rfp_summary", "AR-RFP-1403-07", "en", ("f",), ("AR-RFP-1403-07", "AR-ISS-024", "AR-ISS-024/WEB"))
FULL = "AR-RFP-1403-07, AR-ISS-024 and AR-ISS-024/WEB."


class Script:
    """Returns the scripted generations in order and records the retry notes."""

    def __init__(self, *outputs: Generated) -> None:
        self.outputs = list(outputs)
        self.notes: list[str] = []

    def __call__(self, job: IdJob, variant: str, note: str) -> Generated:
        self.notes.append(note)
        return self.outputs.pop(0)


def accept_all(job: IdJob, text: str) -> tuple[bool, int]:
    return True, 19


def clean(text: str = FULL) -> Generated:
    return Generated(text, grounded=True)


def inventing(text: str = FULL + " AR-ISS-999.") -> Generated:
    return Generated(text, grounded=True, invented=("AR-ISS-999",))


# ---- invented-id guard -------------------------------------------------------------------------

def test_variant_groups() -> None:
    assert RETRY_VARIANTS == {IdVariant.LISTED_RETRY, IdVariant.LISTED_GUARDED}
    assert LISTED_VARIANTS == {IdVariant.LISTED, *RETRY_VARIANTS}
    assert IdVariant("listed_guarded") is IdVariant.LISTED_GUARDED


def test_guard_note_english() -> None:
    note = guard_note(["AR-ISS-024/WEB"], ["AR-ISS-999"], ["AR-ISS-024", "AR-ISS-024/WEB"], "en")
    assert "remove them: AR-ISS-999" in note and "required ids: AR-ISS-024/WEB" in note
    assert "Only these ids are allowed: AR-ISS-024, AR-ISS-024/WEB" in note


def test_guard_note_persian_and_empty_parts() -> None:
    fa = guard_note([], ["AR-ISS-999"], ["AR-ISS-024"], "fa")
    assert "AR-ISS-999" in fa and "فقط این شناسه‌ها مجازند: AR-ISS-024" in fa and "الزامی" not in fa
    only = guard_note([], [], [], "en")
    assert only.startswith("Only these ids are allowed: -.")


def test_guard_rank_order() -> None:
    ranks = [guard_rank("timeout", (), ()), guard_rank("", ("X",), ()), guard_rank("", (), ("Y", "Z")),
             guard_rank("", (), ())]
    assert sorted(ranks) == [(0, 0, 0), (0, 0, 2), (0, 1, 0), (1, 0, 0)]


def test_guarded_retries_an_invented_id() -> None:
    model = Script(inventing(), clean())
    row = IdVariantRunner(model, accept_all).run(JOB, "listed_guarded")
    assert row.attempts == 2 and row.accepted and row.invented == () and row.all_ids
    assert model.notes[0] == "" and "AR-ISS-999" in model.notes[1]


def test_listed_retry_does_not_guard_invented_ids() -> None:
    model = Script(inventing())
    row = IdVariantRunner(model, accept_all).run(JOB, "listed_retry")
    assert row.attempts == 1 and not row.accepted and row.invented == ("AR-ISS-999",)


def test_guarded_no_retry_for_a_clean_complete_text() -> None:
    model = Script(clean())
    row = IdVariantRunner(model, accept_all).run(JOB, "listed_guarded")
    assert row.attempts == 1 and row.accepted and model.notes == [""]


def test_guarded_retries_missing_ids() -> None:
    model = Script(clean("AR-RFP-1403-07 and AR-ISS-024."), clean())
    row = IdVariantRunner(model, accept_all).run(JOB, "listed_guarded")
    assert row.attempts == 2 and row.mentioned == 3 and row.accepted
    assert "AR-ISS-024/WEB" in model.notes[1] and "Only these ids are allowed" in model.notes[1]


def test_guarded_keeps_first_text_on_a_tie() -> None:
    model = Script(inventing(), inventing())
    row = IdVariantRunner(model, accept_all).run(JOB, "listed_guarded")
    assert row.attempts == 2 and not row.accepted and row.invented == ("AR-ISS-999",)


def test_guarded_keeps_first_text_when_retry_fails() -> None:
    model = Script(clean("AR-RFP-1403-07 and AR-ISS-024."), Generated(error="timeout"))
    row = IdVariantRunner(model, accept_all).run(JOB, "listed_guarded")
    assert row.attempts == 2 and row.error == "" and row.mentioned == 2


def test_guarded_first_error_is_not_retried() -> None:
    model = Script(Generated(error="timeout"))
    row = IdVariantRunner(model, accept_all).run(JOB, "listed_guarded")
    assert row.attempts == 1 and row.error == "timeout" and not row.accepted


def test_invented_ids_metric_picks_the_guarded_variant() -> None:
    model = Script(inventing(), inventing(), inventing(), clean())
    rows = IdVariantRunner(model, accept_all).run_all([JOB], ["baseline", "listed_retry", "listed_guarded"])
    cands = {c.variant_id: c for c in id_candidates(rows)}
    assert cands["listed_retry"].value("invented_ids") == 1 and cands["listed_guarded"].value("invented_ids") == 0
    rule = SelectionRule("accept_rate", True, (("invented_ids", False),), 0.0)
    picked = choose("ai_ids", "listed_guarded", list(cands.values()), rule, "baseline")
    assert picked.measured.winner == "listed_guarded" and picked.agrees


# ---- fact pre-check ----------------------------------------------------------------------------

def answer(output: str, facts: tuple = (("30",), ("4",)), kind: OutputKind = OutputKind.QA_ANSWER,
           language: str = "en", gold: str = "") -> JudgeCase:
    return JudgeCase("A1", kind, language, "q", output, expectation=Expectation(facts=facts), gold=gold)


def summary(output: str, **exp: object) -> JudgeCase:
    return JudgeCase("S1", OutputKind.IKE_SUMMARY, "en", "summary", output,
                     expectation=Expectation(status="summary", **exp))


def test_precheck_flags_a_dropped_fact() -> None:
    finding = fact_precheck(answer("Response within 30 minutes."))
    assert finding.applied and not finding.passed and finding.reasons == ("facts:1/2",)


def test_precheck_passes_complete_answers_in_both_scripts() -> None:
    assert fact_precheck(answer("Response within 30 minutes and restoration within 4 hours.")).passed
    fa = answer("پاسخ ظرف ۳۰ دقیقه و رفع موقت ظرف ۴ ساعت است.", facts=(("30", "۳۰"), ("4", "۴")), language="fa")
    assert fact_precheck(fa).passed


def test_precheck_not_applied_to_refusals_or_unknown_facts() -> None:
    refusal = fact_precheck(answer("Not in my documents.", kind=OutputKind.QA_REFUSAL))
    no_facts = fact_precheck(answer("Anything.", facts=()))
    assert not refusal.applied and refusal.passed and not no_facts.applied and no_facts.passed


def test_precheck_summary_ids() -> None:
    case = summary("AR-ISS-024/WEB led by Sara; AR-ISS-024/WIN.", items=("AR-ISS-024/WEB",),
                   item_leads=(("AR-ISS-024/WIN", ("Sara",)),), gaps=("AR-ISS-031",))
    assert required_summary_ids(case) == ("AR-ISS-024/WEB", "AR-ISS-024/WIN", "AR-ISS-031")
    assert fact_precheck(case).reasons == ("missing_id:AR-ISS-031",)
    assert not fact_precheck(summary("No ids known.")).applied


def test_precheck_summary_counts() -> None:
    findings = [PrecheckFinding("ok", True), PrecheckFinding("bad", True, ("facts:0/1",)),
                PrecheckFinding("wrong", True, ("facts:1/2",)), PrecheckFinding("ref", False)]
    out = precheck_summary(findings, {"ok": "accept", "bad": "reject", "wrong": "accept", "ref": "reject"},
                           {"bad": "drop_fact"})
    assert (out["cases"], out["applied"], out["flagged"]) == (4, 3, 2)
    assert (out["gold_rejects_flagged"], out["gold_rejects"]) == (1, 2)
    assert out["false_flags"] == ["wrong"] and out["by_mutation"] == {"drop_fact": "1/1"}
    assert findings[1].to_dict() == {"case_id": "bad", "applied": True, "passed": False, "reasons": ["facts:0/1"]}


class Inner:
    name = "llm:strict"

    def __init__(self, policy: object = None) -> None:
        self.calls = 0
        if policy is not None:
            self.policy = policy

    def judge(self, case: JudgeCase) -> JudgeResult:
        self.calls += 1
        return JudgeResult.for_case(case, self.name, {}, PolicyOutcome(Decision.ACCEPT, 20, 20))


def test_prechecked_judge_rejects_without_a_model_call() -> None:
    inner = Inner()
    judge = PrecheckedJudge(inner, name="strict_precheck")
    result = judge.judge(answer("Response within 30 minutes.", gold="reject"))
    assert result.decision is Decision.REJECT and result.total == 0 and result.parse_mode == "precheck"
    assert result.judge == "strict_precheck" and inner.calls == 0
    assert (judge.prechecked, judge.model_calls) == (1, 0)


def test_prechecked_judge_passes_the_rest_to_the_inner_judge() -> None:
    inner = Inner()
    judge = PrecheckedJudge(inner, name="strict_precheck")
    result = judge.judge(answer("Within 30 minutes; restored within 4 hours."))
    assert result.accepted and result.judge == "strict_precheck" and inner.calls == 1
    assert (judge.prechecked, judge.model_calls) == (0, 1)


def test_prechecked_judge_uses_the_inner_rubric_size() -> None:
    policy = SimpleNamespace(rubric=SimpleNamespace(out_of=25))
    judge = PrecheckedJudge(Inner(policy))
    assert judge.policy is policy
    assert judge.judge(answer("Nothing.")).outcome.out_of == 25


@pytest.mark.slow
def test_precheck_on_the_shipped_calibration() -> None:
    base = load_calibration(CALIBRATION)
    derived = derive_calibration(shipped_items())
    cases = [*base, *(d.case for d in derived)]
    mutation = {d.case.case_id: d.mutation for d in derived if d.mutation}
    findings = [fact_precheck(c) for c in cases]
    out = precheck_summary(findings, {c.case_id: c.gold for c in cases}, mutation)
    assert out["cases"] == 42 and out["false_flags"] == []
    assert out["by_mutation"]["drop_fact"] == "3/3" and out["by_mutation"]["refuse_answerable"] == "2/2"
    assert {"CAL-N01", "CAL-N04"} <= set(out["flagged_ids"])


# ---- new defaults ------------------------------------------------------------------------------

def test_phase15_defaults_and_reasons() -> None:
    s = load_eval_settings(CONFIG)
    assert "strict_precheck" in JUDGE_VARIANTS and s.live.max_judge_calls >= 3 * 42
    reasons = {kind: s.selection[kind].reason for kind in ("retrieval", "qa_prompt")}
    assert "62/62" in reasons["retrieval"] and "switched in Phase 15" in reasons["retrieval"]
    assert "62 of 62" in reasons["qa_prompt"] and "switched in Phase 15" in reasons["qa_prompt"]
