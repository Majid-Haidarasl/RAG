"""Build one node's TransferPackage for one processing cycle.

Input: the sender's own ``NodeKnowledge`` (owned active documents, issues and
sub-issues it owns or supports, executors at the node) plus the accepted
packages its children sent upward in the same cycle. The receiving layer's
``DetailLevelRule`` decides the shape:

1. merge own and received items (one copy per item id, owner's copy first);
2. drop closed items when the level does not show them;
3. one line per item (``items``) or one group per parent issue (``by_issue``);
4. keep the best-ranked ``max_items`` units; list the others as ``omitted``;
5. if a language version is longer than ``max_words``, keep one unit less and
   render again (never below one unit);
6. assemble the Phase 3 ``TransferPackage`` (L0 required fields and citations).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any

from rag_core.knowledge.domain.services import Citation
from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.identifiers import DocumentId, NodeIdentifier
from rag_core.shared_kernel.language import LanguageCode
from rag_core.transfer.domain.items import (
    CapacitySummary,
    IssueGroup,
    NodeKnowledge,
    TransferItem,
    group_items,
    merge_items,
    single_groups,
)
from rag_core.transfer.domain.levels import AggregationMode, DetailLevelRule
from rag_core.transfer.domain.model import TransferPackage
from rag_core.transfer.domain.render import RenderedPackage, RenderInput, render

LANGUAGES = ("fa", "en")


@dataclass
class PackageDraft:
    """A rendered package before review (status ``draft``)."""

    cycle_id: str
    source_node: str
    source_layer: int
    target_node: str
    target_layer: int
    rule: DetailLevelRule
    items: tuple[TransferItem, ...]
    omitted: tuple[str, ...]
    capacity: CapacitySummary
    citations: tuple[str, ...]
    rendered: RenderedPackage
    package: TransferPackage
    received_from: tuple[str, ...] = ()
    expected_children: int = 0
    dropped_closed: tuple[str, ...] = ()
    trimmed: int = 0
    events: list[str] = field(default_factory=list)

    @property
    def detail_level(self) -> str:
        return self.rule.level.value

    @property
    def facts(self) -> tuple[str, ...]:
        return self.rendered.facts

    def text(self, language: str) -> str:
        if language not in LANGUAGES:
            raise InvariantError(f"unsupported package language {language!r}")
        return self.rendered.persian if language == "fa" else self.rendered.english

    def words(self, language: str) -> int:
        return self.rendered.words(language)

    def content_dict(self) -> dict[str, Any]:
        """Everything that defines the package content (no timestamps, no timings)."""
        return {
            "cycle_id": self.cycle_id,
            "source_node": self.source_node,
            "source_layer": self.source_layer,
            "target_node": self.target_node,
            "target_layer": self.target_layer,
            "detail_level": self.detail_level,
            "items": [i.to_dict() for i in self.items],
            "omitted": list(self.omitted),
            "dropped_closed": list(self.dropped_closed),
            "capacity": self.capacity.to_dict(),
            "citations": list(self.citations),
            "facts": list(self.rendered.facts),
            "text_en": self.rendered.english,
            "text_fa": self.rendered.persian,
            "fields": dict(self.package.fields),
            "received_from": list(self.received_from),
            "expected_children": self.expected_children,
            "trimmed": self.trimmed,
        }


def _citation(text: str) -> Citation:
    doc, _, version = text.partition("@")
    return Citation(DocumentId(doc), version, LanguageCode.FA)


class TransferPackageBuilder:
    """Pure domain service. ``versions`` maps document id → active version (Phase 5)."""

    def __init__(self, versions: Mapping[str, str] | None = None) -> None:
        self.versions = dict(versions or {})

    def _citations(
        self,
        sender: NodeKnowledge,
        items: list[TransferItem],
        rule: DetailLevelRule,
        received: list[Any],
    ) -> tuple[str, ...]:
        wanted: list[str] = []
        if rule.aggregation is AggregationMode.ITEMS:
            wanted.extend(d.document_id for d in sender.documents)
        for item in items:
            if item.issue is not None:
                wanted.append(item.issue.issue_id)
            wanted.extend(item.documents)
        out: list[str] = []
        seen: set[str] = set()
        own_versions = {d.document_id: d.version for d in sender.documents}
        for doc in wanted:
            version = own_versions.get(doc) or self.versions.get(doc)
            if not version or doc in seen:
                continue
            seen.add(doc)
            out.append(f"{doc}@{version}")
        return tuple(sorted(out))

    def build(
        self,
        cycle_id: str,
        sender: NodeKnowledge,
        target_node: str,
        rule: DetailLevelRule,
        received: list[Any] | tuple[Any, ...] = (),
        *,
        expected_children: int = 0,
    ) -> PackageDraft:
        if target_node == sender.node_id:
            raise InvariantError("a node cannot send a package to itself")
        children = list(received)
        pool = merge_items([*sender.items, *(i for p in children for i in p.items)])
        dropped: tuple[str, ...] = ()
        if not rule.include_closed:
            dropped = tuple(i.item_id for i in pool if not i.is_open)
            pool = [i for i in pool if i.is_open]
        units: list[IssueGroup] = (
            group_items(pool)
            if rule.aggregation is AggregationMode.BY_ISSUE
            else single_groups(pool)
        )
        capacity = CapacitySummary.of(sender.executors)
        for p in children:
            capacity = capacity.plus(p.capacity)
        if rule.show_capacity != "per_person":
            capacity = replace(capacity, people=())
        child_omitted = tuple(o for p in children for o in p.omitted)
        n = min(rule.max_items, len(units))
        limit = n
        while True:
            selected = units[:n]
            omitted = tuple(
                dict.fromkeys(
                    [*(i for g in units[n:] for i in g.item_ids), *child_omitted]
                )
            )
            items = [i for g in selected for i in g.items]
            citations = self._citations(sender, items, rule, children)
            inp = RenderInput(
                cycle_id=cycle_id,
                source_node=sender.node_id,
                source_name_en=sender.name_en,
                source_name_fa=sender.name_fa,
                target_node=target_node,
                target_layer=rule.receiving_layer,
                rule=rule,
                groups=tuple(selected),
                omitted=omitted,
                capacity=capacity,
                citations=citations,
                received=len(children),
                expected_children=expected_children,
            )
            rendered = render(inp)
            fits = all(rendered.words(lang) <= rule.max_words for lang in LANGUAGES)
            if fits or n <= 1:
                break
            n -= 1
        if not fits:
            longest = max(rendered.words(lang) for lang in LANGUAGES)
            raise InvariantError(
                f"{sender.node_id}: package has {longest} words, max is {rule.max_words}"
            )
        package = TransferPackage.assemble(
            source_node=NodeIdentifier(sender.node_id),
            target_node=NodeIdentifier(target_node),
            rules=rule.ruleset(),
            fields=rendered.fields,
            citations=[_citation(c) for c in citations],
        )
        return PackageDraft(
            cycle_id=cycle_id,
            source_node=sender.node_id,
            source_layer=sender.layer,
            target_node=target_node,
            target_layer=rule.receiving_layer,
            rule=rule,
            items=tuple(items),
            omitted=omitted,
            capacity=capacity,
            citations=citations,
            rendered=rendered,
            package=package,
            received_from=tuple(p.source_node for p in children),
            expected_children=expected_children,
            dropped_closed=dropped,
            trimmed=limit - n,
        )
