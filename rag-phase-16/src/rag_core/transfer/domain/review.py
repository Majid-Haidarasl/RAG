"""Review of a drafted package: fact check, then the judge, then accept or reject.

* Fact check — the shared-kernel ``FactValidator`` (Phase 8
  ``CitedFactValidator``): every identifier and number in the Persian and in
  the English text must occur in the package facts.
* Judge — any ``PackageJudgePort``: the Phase 10 rule judge offline; the rule
  judge **and** qwen3:8b together (combined judge) when Ollama is used.
  The acceptance threshold is the Phase 10 one: 18/20 and every criterion at
  or above its minimum.

Only accepted packages are passed upward by the cycle processor; rejected
packages are still stored, so the reason stays visible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Protocol

from rag_core.shared_kernel.fact_ports import FactValidator, FactVerdict
from rag_core.transfer.domain.builder import LANGUAGES, PackageDraft
from rag_core.transfer.domain.items import CapacitySummary, TransferItem
from rag_core.transfer.domain.model import PackageStatus


@dataclass(frozen=True)
class GroundingCheck:
    grounded: bool
    unsupported: tuple[str, ...] = ()
    flagged: tuple[str, ...] = ()
    claims: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "grounded": self.grounded,
            "unsupported": list(self.unsupported),
            "flagged": list(self.flagged),
            "claims": self.claims,
        }


def ground(
    text: str, facts: tuple[str, ...] | list[str], validator: FactValidator
) -> GroundingCheck:
    report = validator.validate(text, ["\n".join(facts)])
    unsupported = tuple(
        r.claim.raw_text for r in report.results if r.verdict is FactVerdict.UNSUPPORTED
    )
    flagged = tuple(
        r.claim.raw_text for r in report.results if r.verdict is FactVerdict.FLAGGED
    )
    return GroundingCheck(
        not unsupported and not flagged, unsupported, flagged, len(report.results)
    )


@dataclass(frozen=True)
class JudgeVerdict:
    judge: str
    language: str
    total: int
    out_of: int
    accepted: bool
    scores: dict[str, int] = field(default_factory=dict)
    reasons: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "judge": self.judge,
            "language": self.language,
            "total": self.total,
            "out_of": self.out_of,
            "accepted": self.accepted,
            "scores": dict(self.scores),
            "reasons": list(self.reasons),
            "notes": list(self.notes),
        }


class PackageJudgePort(Protocol):
    name: str

    def judge_package(
        self, draft: PackageDraft, language: str, text: str | None = None
    ) -> list[JudgeVerdict]: ...


@dataclass(frozen=True)
class PackageReview:
    grounding: dict[str, GroundingCheck]
    verdicts: tuple[JudgeVerdict, ...]
    accepted: bool
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "grounding": {k: v.to_dict() for k, v in self.grounding.items()},
            "verdicts": [v.to_dict() for v in self.verdicts],
            "accepted": self.accepted,
            "reasons": list(self.reasons),
        }

    def total(self, judge: str, language: str) -> int | None:
        for v in self.verdicts:
            if v.judge == judge and v.language == language:
                return v.total
        return None


class PackageReviewer:
    def __init__(
        self,
        validator: FactValidator,
        judge: PackageJudgePort | None = None,
        languages: tuple[str, ...] = LANGUAGES,
    ) -> None:
        self.validator = validator
        self.judge = judge
        self.languages = languages

    def review(self, draft: PackageDraft) -> BuiltPackage:
        grounding = {
            lang: ground(draft.text(lang), draft.facts, self.validator)
            for lang in self.languages
        }
        reasons = [
            f"ungrounded_{lang}:" + ",".join([*g.unsupported, *g.flagged][:5])
            for lang, g in grounding.items()
            if not g.grounded
        ]
        verdicts: list[JudgeVerdict] = []
        if self.judge is not None:
            for lang in self.languages:
                verdicts.extend(self.judge.judge_package(draft, lang))
        reasons += [
            f"{v.judge}_{v.language}:{v.total}/{v.out_of}"
            for v in verdicts
            if not v.accepted
        ]
        review = PackageReview(grounding, tuple(verdicts), not reasons, tuple(reasons))
        if review.accepted:
            draft.package.accept()
        else:
            draft.package.reject("; ".join(reasons))
        return BuiltPackage(draft, review)


def content_hash(content: dict[str, Any]) -> str:
    raw = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PackageRecord:
    """What the store keeps for one (cycle, source node) revision."""

    cycle_id: str
    source_node: str
    target_node: str
    target_layer: int
    detail_level: str
    status: str
    words_en: int
    words_fa: int
    items: int
    content_hash: str
    payload: dict[str, Any]


@dataclass
class BuiltPackage:
    """A reviewed package: the draft, the review and the Phase 3 aggregate (accepted / rejected)."""

    draft: PackageDraft
    review: PackageReview | None = None

    @property
    def source_node(self) -> str:
        return self.draft.source_node

    @property
    def target_node(self) -> str:
        return self.draft.target_node

    @property
    def target_layer(self) -> int:
        return self.draft.target_layer

    @property
    def detail_level(self) -> str:
        return self.draft.detail_level

    @property
    def items(self) -> tuple[TransferItem, ...]:
        return self.draft.items

    @property
    def omitted(self) -> tuple[str, ...]:
        return self.draft.omitted

    @property
    def capacity(self) -> CapacitySummary:
        return self.draft.capacity

    @property
    def status(self) -> str:
        return self.draft.package.status.value

    @property
    def accepted(self) -> bool:
        return self.draft.package.status is PackageStatus.ACCEPTED

    def content(self) -> dict[str, Any]:
        data = self.draft.content_dict()
        data["status"] = self.status
        data["review"] = self.review.to_dict() if self.review else None
        return data

    def to_record(self) -> PackageRecord:
        content = self.content()
        return PackageRecord(
            cycle_id=self.draft.cycle_id,
            source_node=self.source_node,
            target_node=self.target_node,
            target_layer=self.target_layer,
            detail_level=self.detail_level,
            status=self.status,
            words_en=self.draft.words("en"),
            words_fa=self.draft.words("fa"),
            items=len(self.items),
            content_hash=content_hash(content),
            payload=content,
        )
