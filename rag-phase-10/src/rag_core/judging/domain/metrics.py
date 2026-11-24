"""Aggregate judge results: acceptance, agreement with gold labels, agreement between judges."""

from __future__ import annotations

from collections.abc import Iterable

from rag_core.judging.domain.results import JudgeResult
from rag_core.judging.domain.threshold import Decision


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 3) if values else None


def acceptance(results: Iterable[JudgeResult]) -> dict[str, object]:
    rows = list(results)
    scored = [r for r in rows if r.decision is not Decision.ERROR]
    accepted = [r for r in rows if r.accepted]
    keys: list[str] = []
    for r in scored:
        for k in r.scores:
            if k not in keys:
                keys.append(k)
    by_origin: dict[str, list[int]] = {}
    for r in rows:
        acc_n = by_origin.setdefault(r.origin or "-", [0, 0])
        acc_n[0] += int(r.accepted)
        acc_n[1] += 1
    return {
        "n": len(rows),
        "accepted": len(accepted),
        "rejected": sum(1 for r in rows if r.decision is Decision.REJECT),
        "errors": len(rows) - len(scored),
        "rate": round(len(accepted) / len(rows), 3) if rows else None,
        "mean_total": _mean([float(r.total) for r in scored]),
        "min_total": min((r.total for r in scored), default=None),
        "criterion_means": {
            k: _mean([float(r.scores[k]) for r in scored if k in r.scores])
            for k in keys
        },
        "by_origin": {k: {"accepted": v[0], "n": v[1]} for k, v in by_origin.items()},
        "rejected_cases": [f"{r.case_id}({r.total})" for r in rows if not r.accepted],
    }


def gold_metrics(
    results: Iterable[JudgeResult], *, exclude_tags: tuple[str, ...] = ()
) -> dict[str, object]:
    rows = [r for r in results if r.gold and not set(exclude_tags) & set(r.tags)]
    positives = [r for r in rows if r.gold == "accept"]
    negatives = [r for r in rows if r.gold == "reject"]
    agree = [r for r in rows if r.agrees_with_gold]
    return {
        "n": len(rows),
        "agree": len(agree),
        "accuracy": round(len(agree) / len(rows), 3) if rows else None,
        "positives": len(positives),
        "positives_accepted": sum(1 for r in positives if r.accepted),
        "negatives": len(negatives),
        "negatives_rejected": sum(1 for r in negatives if not r.accepted),
        "errors": sum(1 for r in rows if r.decision is Decision.ERROR),
        "disagreements": [
            f"{r.case_id}:{r.decision.value}({r.total})"
            for r in rows
            if not r.agrees_with_gold
        ],
    }


def rejection_rate(results: Iterable[JudgeResult]) -> dict[str, object]:
    rows = list(results)
    rejected = [r for r in rows if not r.accepted]
    by_kind: dict[str, list[int]] = {}
    for r in rows:
        kind = r.origin.split(":", 1)[1] if ":" in r.origin else r.origin
        rej_n = by_kind.setdefault(kind, [0, 0])
        rej_n[0] += int(not r.accepted)
        rej_n[1] += 1
    return {
        "n": len(rows),
        "rejected": len(rejected),
        "rate": round(len(rejected) / len(rows), 3) if rows else None,
        "by_kind": {k: {"rejected": v[0], "n": v[1]} for k, v in by_kind.items()},
        "accepted_cases": [f"{r.case_id}({r.total})" for r in rows if r.accepted],
    }


def agreement(
    first: Iterable[JudgeResult], second: Iterable[JudgeResult]
) -> dict[str, object]:
    """Accept/reject agreement of two judges on the same cases, with Cohen's kappa."""
    other = {r.case_id: r for r in second}
    pairs = [(r, other[r.case_id]) for r in first if r.case_id in other]
    n = len(pairs)
    if not n:
        return {"n": 0, "agree": 0, "rate": None, "kappa": None, "disagreements": []}
    agree = sum(1 for a, b in pairs if a.accepted == b.accepted)
    p_o = agree / n
    pa = sum(1 for a, _ in pairs if a.accepted) / n
    pb = sum(1 for _, b in pairs if b.accepted) / n
    p_e = pa * pb + (1 - pa) * (1 - pb)
    kappa = round((p_o - p_e) / (1 - p_e), 3) if 1 - p_e > 1e-9 else None
    return {
        "n": n,
        "agree": agree,
        "rate": round(p_o, 3),
        "kappa": kappa,
        "disagreements": [
            f"{a.case_id}:{a.decision.value}/{b.decision.value}"
            for a, b in pairs
            if a.accepted != b.accepted
        ],
    }
