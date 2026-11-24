"""Use cases of the tuning context. Every outside call comes in as a callable,
so the services run the same way offline (tests, BM25) and live (Ollama)."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
import time
from typing import Any

from rag_core.judging.domain.cases import JudgeCase
from rag_core.judging.domain.results import JudgeResult
from rag_core.judging.domain.threshold import Decision
from rag_core.tuning.domain.metrics import (
    Agreement,
    RankingRow,
    RankingSummary,
    binary_agreement,
    detail_ok,
    mean,
    p95,
    rounded,
    share,
    summarize_ranking,
)
from rag_core.tuning.domain.required_ids import (
    IdRun,
    IdVariant,
    guard_note,
    guard_rank,
    missing_ids,
    retry_note,
    summarize_id_runs,
)
from rag_core.tuning.domain.variants import Candidate, Pick, SelectionRule, pick


# ---- retrieval --------------------------------------------------------------------------
def compare_retrieval(
    variant_ids: Sequence[str], rank: Callable[[str], list[RankingRow]]
) -> dict[str, RankingSummary]:
    return {v: summarize_ranking(rank(v)) for v in variant_ids}


def retrieval_candidates(summaries: Mapping[str, RankingSummary]) -> list[Candidate]:
    return [
        Candidate(
            v,
            {
                "context_facts": s.context_facts,
                "hit_at_1": s.hit_at_1,
                "hit_at_3": s.hit_at_3,
                "hit_at_5": s.hit_at_5,
                "mrr": s.mrr,
                "seconds_avg": s.seconds_avg,
            },
        )
        for v, s in summaries.items()
    ]


# ---- judges -----------------------------------------------------------------------------
@dataclass
class JudgeReport:
    judge: str
    n: int
    errors: int
    agreement: Agreement
    by_mutation: dict[str, str] = field(
        default_factory=dict
    )  # kind -> "rejected/total"
    derived: Agreement | None = None
    base: Agreement | None = None
    avg_s: float | None = None
    p95_s: float | None = None
    wrong: list[str] = field(default_factory=list)

    def metrics(self) -> dict[str, float | None]:
        return {
            "accuracy": self.agreement.accuracy,
            "kappa": self.agreement.kappa,
            "leniency": self.agreement.leniency,
            "avg_s": self.avg_s,
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "judge": self.judge,
            "n": self.n,
            "errors": self.errors,
            "agreement": self.agreement.to_dict(),
            "by_mutation": dict(self.by_mutation),
            "derived": self.derived.to_dict() if self.derived else None,
            "base": self.base.to_dict() if self.base else None,
            "avg_s": self.avg_s,
            "p95_s": self.p95_s,
            "wrong": list(self.wrong),
        }


def _gold_pairs(results: Iterable[JudgeResult]) -> list[tuple[bool, bool]]:
    return [
        (r.accepted, r.gold == "accept")
        for r in results
        if r.gold and r.decision is not Decision.ERROR
    ]


def judge_report(judge: str, results: Sequence[JudgeResult]) -> JudgeReport:
    ok = [r for r in results if r.decision is not Decision.ERROR]
    by: dict[str, list[bool]] = {}
    for r in ok:
        if r.origin.startswith("negative:"):
            by.setdefault(r.origin.split(":", 1)[1], []).append(not r.accepted)
    derived = [r for r in ok if "derived" in r.tags]
    base = [r for r in ok if "derived" not in r.tags]
    seconds = [r.seconds for r in ok if r.seconds]
    return JudgeReport(
        judge=judge,
        n=len(results),
        errors=len(results) - len(ok),
        agreement=binary_agreement(_gold_pairs(ok)),
        by_mutation={k: f"{sum(v)}/{len(v)}" for k, v in sorted(by.items())},
        derived=binary_agreement(_gold_pairs(derived)) if derived else None,
        base=binary_agreement(_gold_pairs(base)) if base else None,
        avg_s=rounded(mean(seconds), 2) if seconds else None,
        p95_s=rounded(p95(seconds), 2) if seconds else None,
        wrong=[r.case_id for r in ok if r.gold and r.agrees_with_gold is False],
    )


def judge_candidates(reports: Mapping[str, JudgeReport]) -> list[Candidate]:
    return [Candidate(k, r.metrics()) for k, r in reports.items()]


# ---- Q&A prompts ------------------------------------------------------------------------
@dataclass(frozen=True)
class AnswerRow:
    item_id: str
    status_ok: bool
    facts: tuple[int, int]
    grounded: bool
    citations: tuple[int, int]  # (valid, total)
    rule_accepted: bool | None
    detail_ok: bool
    seconds: float

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.item_id,
            "status_ok": self.status_ok,
            "facts": f"{self.facts[0]}/{self.facts[1]}",
            "grounded": self.grounded,
            "citations": f"{self.citations[0]}/{self.citations[1]}",
            "rule_accepted": self.rule_accepted,
            "detail_ok": self.detail_ok,
            "seconds": round(self.seconds, 2),
        }


def answer_row(
    item_id: str,
    detail: str,
    answer: Mapping[str, Any],
    *,
    status_ok: bool,
    facts: tuple[int, int],
    rule_accepted: bool | None,
) -> AnswerRow:
    citations = list(answer.get("citations") or [])
    valid = sum(1 for c in citations if c.get("valid"))
    answered = answer.get("status") == "answered"
    text = str(answer.get("text") or "")
    timings = answer.get("timings_s") or {}
    return AnswerRow(
        item_id,
        status_ok,
        facts,
        bool(answer.get("grounded")) if answered else True,
        (valid, len(citations)),
        rule_accepted,
        detail_ok(text, detail if answered else "refusal"),
        float(timings.get("generation", 0.0) or 0.0),
    )


@dataclass
class PromptSummary:
    variant: str
    n: int = 0
    status_ok: int = 0
    facts_hit: int = 0
    facts_total: int = 0
    grounded: int = 0
    citations_valid: int = 0
    citations_total: int = 0
    rule_accepted: int = 0
    rule_judged: int = 0
    detail_ok: int = 0
    generation_avg_s: float | None = None
    generation_p95_s: float | None = None
    rows: list[AnswerRow] = field(default_factory=list)

    def metrics(self) -> dict[str, float | None]:
        return {
            "facts": share(self.facts_hit, self.facts_total),
            "status_ok": share(self.status_ok, self.n),
            "grounded": share(self.grounded, self.n),
            "citation_validity": share(self.citations_valid, self.citations_total),
            "rule_accept": share(self.rule_accepted, self.rule_judged),
            "detail_ok": share(self.detail_ok, self.n),
            "generation_avg_s": self.generation_avg_s,
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "variant": self.variant,
            "n": self.n,
            "status_ok": f"{self.status_ok}/{self.n}",
            "facts": f"{self.facts_hit}/{self.facts_total}",
            "grounded": f"{self.grounded}/{self.n}",
            "citations": f"{self.citations_valid}/{self.citations_total}",
            "rule_accepted": f"{self.rule_accepted}/{self.rule_judged}",
            "detail_ok": f"{self.detail_ok}/{self.n}",
            "generation_avg_s": self.generation_avg_s,
            "generation_p95_s": self.generation_p95_s,
            "metrics": self.metrics(),
            "rows": [r.to_dict() for r in self.rows],
        }


def summarize_prompt(variant: str, rows: Sequence[AnswerRow]) -> PromptSummary:
    s = PromptSummary(variant, n=len(rows), rows=list(rows))
    for r in rows:
        s.status_ok += r.status_ok
        s.facts_hit += r.facts[0]
        s.facts_total += r.facts[1]
        s.grounded += r.grounded
        s.citations_valid += r.citations[0]
        s.citations_total += r.citations[1]
        if r.rule_accepted is not None:
            s.rule_judged += 1
            s.rule_accepted += r.rule_accepted
        s.detail_ok += r.detail_ok
    gen = [r.seconds for r in rows if r.seconds]
    s.generation_avg_s = rounded(mean(gen), 2) if gen else None
    s.generation_p95_s = rounded(p95(gen), 2) if gen else None
    return s


# ---- required ids -----------------------------------------------------------------------
@dataclass(frozen=True)
class Generated:
    """What one generation produced: the parsed text (or an error) and the grounding check."""

    text: str = ""
    error: str = ""
    grounded: bool = False
    invented: tuple[str, ...] = ()


class IdVariantRunner:
    """Runs one job with one id variant. ``generate(job, variant, note)`` returns ``Generated``;
    ``accept(job, text)`` returns (accepted, rule total). ``listed_retry`` asks once more,
    naming the missing ids, when the first text missed any. ``listed_guarded`` also asks once
    more when the first text invented an id, keeps the text with fewer invented ids (then fewer
    missing ids) and rejects a text that still invents one."""

    def __init__(
        self,
        generate: Callable[[Any, str, str], Generated],
        accept: Callable[[Any, str], tuple[bool, int | None]],
    ) -> None:
        self.generate = generate
        self.accept = accept

    def run(self, job: Any, variant: str) -> IdRun:
        t0 = time.perf_counter()
        attempts = 1
        out = self.generate(job, variant, "")
        if variant == IdVariant.LISTED_GUARDED:
            out, attempts = self._guarded(job, variant, out)
        elif (
            variant == IdVariant.LISTED_RETRY
            and not out.error
            and missing_ids(out.text, job.required)
        ):
            attempts = 2
            again = self.generate(
                job,
                variant,
                retry_note(missing_ids(out.text, job.required), job.language),
            )
            if not again.error and len(missing_ids(again.text, job.required)) <= len(
                missing_ids(out.text, job.required)
            ):
                out = again
        seconds = time.perf_counter() - t0
        if out.error:
            return IdRun(
                job.task,
                job.subject,
                job.language,
                variant,
                0,
                len(job.required),
                False,
                (),
                False,
                attempts,
                seconds,
                out.error,
            )
        missed = missing_ids(out.text, job.required)
        accepted, total = self.accept(job, out.text)
        return IdRun(
            job.task,
            job.subject,
            job.language,
            variant,
            len(job.required) - len(missed),
            len(job.required),
            out.grounded,
            out.invented,
            accepted and out.grounded and not out.invented,
            attempts,
            seconds,
            "",
            total,
        )

    def _guarded(self, job: Any, variant: str, out: Generated) -> tuple[Generated, int]:
        if out.error:
            return out, 1
        missed = missing_ids(out.text, job.required)
        if not missed and not out.invented:
            return out, 1
        again = self.generate(
            job, variant, guard_note(missed, out.invented, job.required, job.language)
        )
        first = guard_rank(out.error, out.invented, missed)
        second = guard_rank(
            again.error,
            again.invented,
            missing_ids(again.text, job.required)
            if not again.error
            else tuple(job.required),
        )
        return (again if second < first else out), 2

    def run_all(
        self,
        jobs: Iterable[Any],
        variants: Sequence[str],
        progress: Callable[[IdRun], None] | None = None,
    ) -> list[IdRun]:
        rows: list[IdRun] = []
        for job in jobs:
            for v in variants:
                row = self.run(job, v)
                rows.append(row)
                if progress is not None:
                    progress(row)
        return rows


def id_candidates(rows: Iterable[IdRun]) -> list[Candidate]:
    return [
        Candidate(
            v,
            {
                "accept_rate": s["accept_rate"],
                "mention_rate": s["mention_rate"],
                "invented_ids": s["invented_ids"],
                "seconds_avg": s["seconds_avg"],
            },
        )
        for v, s in summarize_id_runs(rows).items()
    ]


# ---- choosing ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Choice:
    kind: str
    configured: str
    measured: Pick | None

    @property
    def agrees(self) -> bool | None:
        if self.measured is None or not self.measured.measured:
            return None
        return self.measured.winner == self.configured

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "configured": self.configured,
            "measured": self.measured.to_dict() if self.measured else None,
            "agrees": self.agrees,
        }


def choose(
    kind: str,
    configured: str,
    candidates: Sequence[Candidate],
    rule: SelectionRule | None,
    baseline: str,
) -> Choice:
    if (
        rule is None
        or not candidates
        or baseline not in {c.variant_id for c in candidates}
    ):
        return Choice(kind, configured, None)
    return Choice(kind, configured, pick(candidates, rule, baseline))


def judge_cases_by_id(cases: Iterable[JudgeCase]) -> dict[str, JudgeCase]:
    return {c.case_id: c for c in cases}
