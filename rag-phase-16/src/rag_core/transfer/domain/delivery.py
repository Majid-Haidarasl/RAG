"""UC-09: deliver the latest accepted transfer package to the parent node."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def score_from_payload(payload: dict[str, Any] | None) -> int | None:
    """Rubric total (out of 20) from the final accepted judge/review verdict.

    When several verdicts exist, the last accepted verdict's ``total`` is used.
    """
    if not payload:
        return None
    review = payload.get("review") or {}
    verdicts = review.get("verdicts") or []
    accepted = [v for v in verdicts if isinstance(v, dict) and v.get("accepted")]
    if not accepted:
        return None
    total = accepted[-1].get("total")
    return None if total is None else int(total)


@dataclass(frozen=True)
class DeliveryResult:
    source_node: str
    revision: int
    content_hash: str
    score: int | None
    warning: str | None = None
    payload: dict[str, Any] | None = None
