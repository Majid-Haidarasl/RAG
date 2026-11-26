"""Near-duplicate detection via embedding cosine similarity.

Pairs at or above ``same_threshold`` are duplicates. Pairs below
``borderline_low`` are distinct. Scores in ``[borderline_low, same_threshold)``
are asked of an LLM (same / different). Unit tests inject fake embedder/chat.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Protocol

from rag_core.rag.domain.vector import cosine
from rag_core.shared_kernel.errors import InvariantError

_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")


@dataclass(frozen=True)
class EmbeddingDedupConfig:
    same_threshold: float = 0.92
    borderline_low: float = 0.75

    def __post_init__(self) -> None:
        if not 0.0 < self.borderline_low <= self.same_threshold <= 1.0:
            raise InvariantError(
                "embedding dedup thresholds must satisfy "
                "0 < borderline_low <= same_threshold <= 1"
            )


@dataclass(frozen=True)
class TextPair:
    left: str
    right: str
    text_left: str
    text_right: str


@dataclass(frozen=True)
class DedupDecision:
    left: str
    right: str
    cosine: float
    verdict: str  # same | different
    source: str  # cosine | llm
    detail: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "left": self.left,
            "right": self.right,
            "cosine": round(self.cosine, 4),
            "verdict": self.verdict,
            "source": self.source,
            "detail": self.detail,
        }


class EmbedderPort(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class DedupChatPort(Protocol):
    def generate(self, system: str, user: str) -> object: ...


SYSTEM = (
    "You decide whether two knowledge texts are near-duplicates of the same content. "
    "Reply with one JSON object only: {\"verdict\": \"same\"} or {\"verdict\": \"different\"}."
)


def _parse_verdict(raw: str) -> str:
    text = _FENCE_RE.sub("", (raw or "").strip()).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise InvariantError("dedup LLM reply has no JSON object") from None
        data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise InvariantError("dedup LLM reply must be a JSON object")
    verdict = str(data.get("verdict", "")).strip().lower()
    if verdict not in {"same", "different"}:
        raise InvariantError(f"dedup LLM verdict must be same|different, got {verdict!r}")
    return verdict


@dataclass
class EmbeddingNearDedup:
    embedder: EmbedderPort
    chat: DedupChatPort | None = None
    config: EmbeddingDedupConfig = field(default_factory=EmbeddingDedupConfig)

    def decide_pair(self, pair: TextPair) -> DedupDecision:
        vectors = self.embedder.embed([pair.text_left, pair.text_right])
        if len(vectors) != 2:
            raise InvariantError("embedder must return one vector per text")
        score = float(cosine(vectors[0], vectors[1]))
        if score >= self.config.same_threshold:
            return DedupDecision(
                pair.left, pair.right, score, "same", "cosine", "above same_threshold"
            )
        if score < self.config.borderline_low:
            return DedupDecision(
                pair.left,
                pair.right,
                score,
                "different",
                "cosine",
                "below borderline_low",
            )
        if self.chat is None:
            raise InvariantError(
                "borderline pair requires a chat model for same/different"
            )
        user = (
            f"Text A ({pair.left}):\n{pair.text_left}\n\n"
            f"Text B ({pair.right}):\n{pair.text_right}\n\n"
            'Return {"verdict": "same"} or {"verdict": "different"}.'
        )
        result = self.chat.generate(SYSTEM, user)
        raw = result.text if hasattr(result, "text") else str(result)
        verdict = _parse_verdict(raw)
        return DedupDecision(
            pair.left, pair.right, score, verdict, "llm", "borderline band"
        )

    def compare(self, pairs: list[TextPair]) -> list[DedupDecision]:
        return [self.decide_pair(p) for p in pairs]
