"""Detail levels: what a package contains, depending on the layer that receives it.

The receiving layer decides the detail level (layer registry column
``default_detail_level_received``, AR-TRN-026 §2–§6):

========  =====================  ===========  ==========================================
receiver  detail level           max words    content
========  =====================  ===========  ==========================================
L3        detailed_technical     3000         (L4 library → L3; not an upward package)
L2        technical_summary      1500         every item: lead, collaborators, dependencies,
                                              documents, knowledge gaps, per-person capacity
L1        managerial             800          grouped by issue: progress, due date, decision
                                              amount, sub-item leads, gap list, capacity counts
L0        executive              400          top issues only: risks, decisions requested,
                                              source references (required fields, AR-TRN-026)
========  =====================  ===========  ==========================================

``max_words`` is checked on each language version (Persian and English) of
the package text separately. Items beyond ``max_items`` are not dropped
silently: their ids are listed as ``omitted``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from rag_core.shared_kernel.errors import InvariantError, NotFoundError
from rag_core.shared_kernel.layer import LayerIndex
from rag_core.transfer.domain.model import TransferDetailLevel, TransferRuleSet

GAP_MODES = ("per_item", "list", "count")
CAPACITY_MODES = ("per_person", "counts", "none")


class AggregationMode(StrEnum):
    ITEMS = "items"          # one line per item
    BY_ISSUE = "by_issue"    # sub-issues grouped under their parent issue


@dataclass(frozen=True)
class DetailLevelRule:
    level: TransferDetailLevel
    receiving_layer: int
    max_items: int                 # items (ITEMS) or issue groups (BY_ISSUE)
    max_words: int                 # per language version
    aggregation: AggregationMode
    include_closed: bool
    show_people: bool
    show_collaborators: bool
    show_documents: bool
    max_documents_per_item: int
    show_gaps: str
    show_capacity: str
    show_dependencies: bool
    citation_level: str
    required_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.level, TransferDetailLevel):
            object.__setattr__(self, "level", TransferDetailLevel(self.level))
        if not isinstance(self.aggregation, AggregationMode):
            object.__setattr__(self, "aggregation", AggregationMode(self.aggregation))
        if self.max_items < 1:
            raise InvariantError("max_items must be >= 1")
        if self.max_words < 50:
            raise InvariantError("max_words must be >= 50")
        if self.show_gaps not in GAP_MODES:
            raise InvariantError(f"show_gaps must be one of {GAP_MODES}")
        if self.show_capacity not in CAPACITY_MODES:
            raise InvariantError(f"show_capacity must be one of {CAPACITY_MODES}")
        if self.show_collaborators and not self.show_people:
            raise InvariantError("collaborators are shown only together with people")
        if self.max_documents_per_item < 0:
            raise InvariantError("max_documents_per_item must be >= 0")
        LayerIndex(self.receiving_layer)

    def ruleset(self) -> TransferRuleSet:
        """The Phase 3 ``TransferRuleSet`` used to assemble the package.

        The word limit is enforced per language by the builder, so the rule set
        itself carries no ``max_words`` (the package holds both languages).
        """
        return TransferRuleSet(LayerIndex(self.receiving_layer), self.level, min_judge_score=18, max_words=None,
                               required_fields=self.required_fields)


DEFAULT_RULES: tuple[DetailLevelRule, ...] = (
    DetailLevelRule(TransferDetailLevel.EXECUTIVE, 0, max_items=3, max_words=400,
                    aggregation=AggregationMode.BY_ISSUE, include_closed=False, show_people=False,
                    show_collaborators=False, show_documents=False, max_documents_per_item=0, show_gaps="count",
                    show_capacity="none", show_dependencies=False, citation_level="document",
                    required_fields=("risks", "decisions_requested", "source_references")),
    DetailLevelRule(TransferDetailLevel.MANAGERIAL, 1, max_items=6, max_words=800,
                    aggregation=AggregationMode.BY_ISSUE, include_closed=False, show_people=True,
                    show_collaborators=False, show_documents=False, max_documents_per_item=0, show_gaps="list",
                    show_capacity="counts", show_dependencies=True, citation_level="document"),
    DetailLevelRule(TransferDetailLevel.TECHNICAL_SUMMARY, 2, max_items=8, max_words=1500,
                    aggregation=AggregationMode.ITEMS, include_closed=True, show_people=True,
                    show_collaborators=True, show_documents=True, max_documents_per_item=3, show_gaps="per_item",
                    show_capacity="per_person", show_dependencies=True, citation_level="document + section"),
    DetailLevelRule(TransferDetailLevel.DETAILED_TECHNICAL, 3, max_items=12, max_words=3000,
                    aggregation=AggregationMode.ITEMS, include_closed=True, show_people=True,
                    show_collaborators=True, show_documents=True, max_documents_per_item=6, show_gaps="per_item",
                    show_capacity="per_person", show_dependencies=True, citation_level="document + section + chunk"),
)


class RuleBook:
    """Detail-level rules indexed by the receiving layer."""

    def __init__(self, rules: tuple[DetailLevelRule, ...] | list[DetailLevelRule] = DEFAULT_RULES) -> None:
        by_layer: dict[int, DetailLevelRule] = {}
        for rule in rules:
            if rule.receiving_layer in by_layer:
                raise InvariantError(f"two rules for receiving layer L{rule.receiving_layer}")
            by_layer[rule.receiving_layer] = rule
        levels = [r.level for r in by_layer.values()]
        if len(set(levels)) != len(levels):
            raise InvariantError("each detail level may be used by one receiving layer only")
        self._by_layer = by_layer

    def for_layer(self, layer: int) -> DetailLevelRule:
        if layer not in self._by_layer:
            raise NotFoundError(f"no detail-level rule for receiving layer L{layer}")
        return self._by_layer[layer]

    def for_level(self, level: TransferDetailLevel | str) -> DetailLevelRule:
        key = TransferDetailLevel(level)
        for rule in self._by_layer.values():
            if rule.level is key:
                return rule
        raise NotFoundError(f"no rule for detail level {key.value}")

    @property
    def rules(self) -> list[DetailLevelRule]:
        return [self._by_layer[k] for k in sorted(self._by_layer)]

    def registry_mismatches(self, layers: dict[int, tuple[str, int | None]]) -> list[str]:
        """Compare with the layer registry: layer → (default_detail_level, max_package_words)."""
        problems: list[str] = []
        for index, (level, words) in sorted(layers.items()):
            if index not in self._by_layer:
                continue
            rule = self._by_layer[index]
            if level and level != rule.level.value:
                problems.append(f"L{index}: registry level {level} != rule {rule.level.value}")
            if words is not None and words != rule.max_words:
                problems.append(f"L{index}: registry max words {words} != rule {rule.max_words}")
        return problems
