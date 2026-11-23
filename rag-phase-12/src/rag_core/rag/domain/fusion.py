"""Reciprocal Rank Fusion (Cormack, Clarke & Büttcher, SIGIR 2009).

``score(d) = Σ_r w_r / (k + rank_r(d))`` with 1-based ranks and k = 60.
RRF needs no score calibration between BM25 (unbounded) and cosine
([-1, 1]), which is why it is used instead of a weighted score sum.
Ties are broken by key so results are deterministic.
"""

from __future__ import annotations

from collections import defaultdict

DEFAULT_RRF_K = 60


def reciprocal_rank_fusion(
    rankings: dict[str, list[str]],
    *,
    k: int = DEFAULT_RRF_K,
    weights: dict[str, float] | None = None,
) -> list[tuple[str, float]]:
    if k < 1:
        raise ValueError("RRF k must be >= 1")
    scores: dict[str, float] = defaultdict(float)
    for name, ranked in rankings.items():
        weight = 1.0 if weights is None else weights.get(name, 1.0)
        seen: set[str] = set()
        rank = 0
        for key in ranked:
            if key in seen:
                continue
            seen.add(key)
            rank += 1
            scores[key] += weight / (k + rank)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
