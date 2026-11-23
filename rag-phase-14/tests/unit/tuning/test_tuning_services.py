"""Phase 14 application services: retrieval / judge / prompt comparisons, the id runner and choices."""

import pytest

from rag_core.judging.domain.results import JudgeResult
from rag_core.judging.domain.threshold import Decision, PolicyOutcome
from rag_core.tuning.application.services import (
    Generated,
    IdVariantRunner,
    answer_row,
    choose,
    compare_retrieval,
    id_candidates,
    judge_candidates,
    judge_report,
    retrieval_candidates,
    summarize_prompt,
)
from rag_core.tuning.domain.metrics import RankingRow
from rag_core.tuning.domain.variants import Candidate, SelectionRule
from rag_core.tuning.infrastructure.ids_acl import IdJob

pytestmark = [pytest.mark.tuning, pytest.mark.eval_metrics]


def result(case_id: str, gold: str, accepted: bool | None, origin: str = "calibration", tags: tuple = (),
           seconds: float = 1.0) -> JudgeResult:
    decision = Decision.ERROR if accepted is None else (Decision.ACCEPT if accepted else Decision.REJECT)
    return JudgeResult(case_id, "llm:x", "qa_answer", origin, gold, {}, PolicyOutcome(decision, 18, 20),
                       seconds=seconds, tags=tags)


def test_compare_retrieval_and_candidates() -> None:
    rows = {"baseline": [RankingRow("a", ("D1",), ("D1",), (1, 2))],
            "wide": [RankingRow("a", ("D1",), ("D1",), (2, 2))]}
    out = compare_retrieval(["baseline", "wide"], lambda v: rows[v])
    assert out["baseline"].context_facts == 0.5 and out["wide"].context_facts == 1.0
    cands = {c.variant_id: c for c in retrieval_candidates(out)}
    assert cands["wide"].value("context_facts") == 1.0 and cands["baseline"].value("hit_at_5") == 1.0


def test_judge_report() -> None:
    results = [result("CAL-01", "accept", True), result("CAL-N01", "reject", True, "negative:wrong_number"),
               result("CAL14-P01-fa-ok", "accept", True, tags=("derived",), seconds=3.0),
               result("CAL14-P01-en-drop_fact", "reject", False, "negative:drop_fact", ("derived", "drop_fact")),
               result("CAL14-P02-en-wrong_number", "reject", False, "negative:wrong_number", ("derived",)),
               result("CAL-02", "accept", None)]
    rep = judge_report("strict", results)
    assert rep.n == 6 and rep.errors == 1 and rep.agreement.n == 5 and rep.agreement.agree == 4
    assert rep.agreement.leniency == 0.333 and rep.wrong == ["CAL-N01"]
    assert rep.by_mutation == {"drop_fact": "1/1", "wrong_number": "1/2"}
    assert rep.derived is not None and rep.derived.accuracy == 1.0 and rep.base is not None and rep.base.n == 2
    assert rep.avg_s == 1.4 and rep.metrics()["accuracy"] == 0.8
    assert rep.to_dict()["by_mutation"]["drop_fact"] == "1/1"


def test_judge_candidates_choose_the_stricter_judge() -> None:
    lenient = judge_report("baseline", [result("a", "accept", True), result("b", "reject", True),
                                        result("c", "reject", True)])
    strict = judge_report("strict", [result("a", "accept", True), result("b", "reject", False),
                                     result("c", "reject", False)])
    rule = SelectionRule("accuracy", True, (("leniency", False),), 0.02)
    choice = choose("judge_prompt", "strict", judge_candidates({"baseline": lenient, "strict": strict}), rule, "baseline")
    assert choice.measured is not None and choice.measured.winner == "strict" and choice.agrees is True


def answer(status: str = "answered", text: str = "A [X §1].", grounded: bool = True, valid: int = 1,
           total: int = 1, gen: float = 2.0) -> dict:
    cites = [{"valid": i < valid} for i in range(total)]
    return {"status": status, "text": text, "grounded": grounded, "citations": cites,
            "timings_s": {"generation": gen}}


def test_answer_row() -> None:
    row = answer_row("GQ-1", "short", answer(valid=1, total=2), status_ok=True, facts=(2, 2), rule_accepted=True)
    assert row.citations == (1, 2) and row.detail_ok and row.seconds == 2.0 and row.grounded
    refusal = answer_row("GQ-2", "short", answer("out_of_scope", "No. Ask N-CEO. Later. Now.", grounded=False,
                                                 total=0), status_ok=False, facts=(0, 0), rule_accepted=None)
    assert refusal.grounded and not refusal.detail_ok and refusal.to_dict()["citations"] == "0/0"


def test_summarize_prompt() -> None:
    rows = [answer_row("a", "short", answer(), status_ok=True, facts=(2, 2), rule_accepted=True),
            answer_row("b", "list", answer(grounded=False, gen=4.0), status_ok=True, facts=(1, 3), rule_accepted=False),
            answer_row("c", "refusal", answer("out_of_scope", "No.", total=0, gen=1.0), status_ok=False, facts=(0, 0),
                       rule_accepted=None)]
    s = summarize_prompt("qa.answer", rows)
    assert (s.n, s.status_ok, s.facts_hit, s.facts_total, s.grounded) == (3, 2, 3, 5, 2)
    assert (s.rule_accepted, s.rule_judged, s.citations_valid, s.citations_total) == (1, 2, 2, 2)
    m = s.metrics()
    assert m["facts"] == 0.6 and m["rule_accept"] == 0.5 and m["generation_avg_s"] == 2.33
    assert s.to_dict()["facts"] == "3/5" and s.generation_p95_s == 4.0


JOB = IdJob("rfp_summary", "AR-RFP-1403-07", "en", ("f",), ("AR-RFP-1403-07", "AR-ISS-024", "AR-ISS-024/WEB"))


class Model:
    def __init__(self, first: str, second: str = "", error: str = "") -> None:
        self.first, self.second, self.error = first, second, error
        self.notes: list[str] = []

    def __call__(self, job: IdJob, variant: str, note: str) -> Generated:
        self.notes.append(note)
        if self.error:
            return Generated(error=self.error)
        return Generated(self.second if note else self.first, grounded=True)


def accept_all(job: IdJob, text: str) -> tuple[bool, int]:
    return True, 19


def test_runner_retries_once_with_the_missing_ids() -> None:
    model = Model("AR-RFP-1403-07 and AR-ISS-024.", "AR-RFP-1403-07, AR-ISS-024 and AR-ISS-024/WEB.")
    row = IdVariantRunner(model, accept_all).run(JOB, "listed_retry")
    assert row.attempts == 2 and row.all_ids and row.accepted and row.rule_total == 19
    assert model.notes[0] == "" and "AR-ISS-024/WEB" in model.notes[1]


def test_runner_no_retry_for_listed_or_complete_text() -> None:
    model = Model("AR-RFP-1403-07 and AR-ISS-024.")
    row = IdVariantRunner(model, accept_all).run(JOB, "listed")
    assert row.attempts == 1 and (row.mentioned, row.expected) == (2, 3) and not row.all_ids
    full = Model("AR-RFP-1403-07 AR-ISS-024 AR-ISS-024/WEB")
    assert IdVariantRunner(full, accept_all).run(JOB, "listed_retry").attempts == 1


def test_runner_keeps_the_better_text() -> None:
    model = Model("AR-RFP-1403-07 and AR-ISS-024.", "nothing useful")
    row = IdVariantRunner(model, accept_all).run(JOB, "listed_retry")
    assert row.attempts == 2 and row.mentioned == 2


def test_runner_errors_and_invented_ids() -> None:
    row = IdVariantRunner(Model("", error="timeout"), accept_all).run(JOB, "baseline")
    assert row.error == "timeout" and not row.accepted and row.mentioned == 0
    invented = IdVariantRunner(lambda j, v, n: Generated("AR-RFP-1403-07 AR-ISS-024 AR-ISS-024/WEB AR-X-1",
                                                         grounded=True, invented=("AR-X-1",)), accept_all)
    assert not invented.run(JOB, "listed").accepted


def test_run_all_and_id_candidates() -> None:
    seen = []
    runner = IdVariantRunner(Model("AR-RFP-1403-07 and AR-ISS-024.", "AR-RFP-1403-07 AR-ISS-024 AR-ISS-024/WEB"),
                             accept_all)
    rows = runner.run_all([JOB], ["baseline", "listed_retry"], progress=seen.append)
    assert [r.variant for r in rows] == ["baseline", "listed_retry"] and len(seen) == 2
    cands = {c.variant_id: c for c in id_candidates(rows)}
    assert cands["listed_retry"].value("mention_rate") == 1.0 and cands["baseline"].value("mention_rate") == 0.667
    rule = SelectionRule("accept_rate", True, (("mention_rate", True),), 0.0)
    pick_ = choose("ai_ids", "listed_retry", list(cands.values()), rule, "baseline")
    assert pick_.measured.winner == "listed_retry" and pick_.agrees


def test_choose_without_measurements() -> None:
    c = choose("qa_prompt", "qa.answer_complete", [], SelectionRule("facts"), "qa.answer")
    assert c.measured is None and c.agrees is None and c.to_dict()["measured"] is None
    c = choose("qa_prompt", "x", [Candidate("qa.answer", {})], None, "qa.answer")
    assert c.measured is None
    c = choose("qa_prompt", "x", [Candidate("qa.answer", {})], SelectionRule("facts"), "qa.answer")
    assert c.measured is not None and not c.measured.measured and c.agrees is None
