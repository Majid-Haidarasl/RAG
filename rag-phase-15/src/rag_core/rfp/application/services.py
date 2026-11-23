"""RFP generation use case: key issues -> candidates -> one draft per blueprint and language."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from rag_core.rfp.domain.blueprint import Blueprint
from rag_core.rfp.domain.generator import (
    Candidate,
    GapView,
    ItemView,
    KeyIssueView,
    RfpDraft,
    build_rfp,
    select_candidates,
)


@dataclass
class RfpRun:
    candidates: list[Candidate] = field(default_factory=list)
    drafts: dict[str, dict[str, RfpDraft]] = field(default_factory=dict)   # rfp id -> language -> draft

    @property
    def sourcing(self) -> list[Candidate]:
        return [c for c in self.candidates if c.has_rfp]

    @property
    def rfp_ids(self) -> list[str]:
        return list(self.drafts)

    def all_drafts(self) -> list[RfpDraft]:
        return [d for by_lang in self.drafts.values() for d in by_lang.values()]

    def to_dict(self) -> dict[str, object]:
        return {"candidates": [c.to_dict() for c in self.candidates],
                "rfps": {k: {lang: d.to_dict() for lang, d in v.items()} for k, v in self.drafts.items()}}


class RfpService:
    def __init__(self, blueprints: Iterable[Blueprint], categories: Iterable[str] = ("procurement",),
                 targets: Mapping[str, str] | None = None,
                 headings: Mapping[str, tuple[str, str]] | None = None) -> None:
        self.blueprints = list(blueprints)
        self.categories = tuple(categories)
        self.targets = dict(targets or {})
        self.headings = dict(headings or {})

    def blueprint(self, blueprint_id: str) -> Blueprint | None:
        return next((b for b in self.blueprints if b.blueprint_id == blueprint_id), None)

    def run(self, key: Sequence[KeyIssueView], gaps: Iterable[GapView], items: Mapping[str, ItemView],
            cycle_id: str, languages: Iterable[str] = ("fa", "en")) -> RfpRun:
        gaps = list(gaps)
        out = RfpRun(select_candidates(key, self.blueprints, self.categories, self.targets))
        key_by_id = {k.issue_id: k for k in key}
        for bp_id in dict.fromkeys(c.blueprint_id for c in out.sourcing):
            bp = self.blueprint(bp_id)
            if bp is None:
                continue
            item_id = next((c.item_id for c in out.sourcing if c.blueprint_id == bp_id and c.item_id), bp.item)
            item = items.get(item_id) if item_id else None
            out.drafts[bp.rfp_id] = {lang: build_rfp(bp, out.candidates, key_by_id, gaps, lang, cycle_id, item,
                                                     self.headings) for lang in languages}
        return out
