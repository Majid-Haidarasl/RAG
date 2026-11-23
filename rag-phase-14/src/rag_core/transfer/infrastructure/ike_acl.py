"""Anti-corruption layer: Phase 9 IKE digest → leads and knowledge lacks per sub-issue."""

from __future__ import annotations

from rag_core.ike.domain.summary import IssueDigest


def leads_and_lacks(d: IssueDigest, names: dict[str, tuple[str, str]]
                    ) -> tuple[dict[str, tuple[str, str, tuple[str, ...], tuple[str, ...]]], dict[str, tuple[str, ...]]]:
    leads: dict[str, tuple[str, str, tuple[str, ...], tuple[str, ...]]] = {}
    lacks: dict[str, tuple[str, ...]] = {}
    for it in d.items:
        lead_en, lead_fa = names.get(it.lead, (it.lead, "")) if it.lead else ("", "")
        collab = [names.get(c, (c, "")) for c in it.collaborators]
        leads[it.item_id] = (lead_en, lead_fa, tuple(en for en, _ in collab), tuple(fa or en for en, fa in collab))
        if it.lacks:
            lacks[it.item_id] = tuple(dict.fromkeys(target for target, _ in it.lacks))
    return leads, lacks
