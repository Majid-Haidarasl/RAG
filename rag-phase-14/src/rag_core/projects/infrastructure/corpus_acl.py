"""Anti-corruption layer: Phase 8 chunk records -> document texts for evidence grounding.

Only chunks of the active version of a document are used (Phase 5 lifecycle).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping


def document_texts(
    records: Iterable[object], versions: Mapping[str, str] | None = None
) -> dict[tuple[str, str], list[str]]:
    out: dict[tuple[str, str], list[str]] = {}
    for r in records:
        if (
            getattr(r, "version_status", "active") != "active"
            or getattr(r, "status", "active") != "active"
        ):
            continue
        doc = str(getattr(r, "document_id"))
        if versions is not None and versions.get(doc) not in (
            None,
            str(getattr(r, "version", "")),
        ):
            continue
        key = (doc, str(getattr(r, "language", "")))
        out.setdefault(key, []).append(str(getattr(r, "text", "")))
    return out
