"""Next action inside one issue: which sub-issue unblocks the most other sub-issues."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

CLOSED = frozenset({"resolved", "closed"})


@dataclass(frozen=True)
class SubTask:
    item_id: str
    status: str
    position: int
    depends_on: tuple[str, ...] = ()   # full sibling ids


@dataclass(frozen=True)
class NextAction:
    item_id: str
    unblocks: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {"item_id": self.item_id, "unblocks": list(self.unblocks)}


def dependents_of(tasks: Iterable[SubTask]) -> dict[str, tuple[str, ...]]:
    """Sub-issue -> open sub-issues that wait for it, directly or through a chain."""
    items = list(tasks)
    direct: dict[str, list[str]] = {t.item_id: [] for t in items}
    for t in items:
        if t.status in CLOSED:
            continue
        for d in t.depends_on:
            direct.setdefault(d, []).append(t.item_id)
    out: dict[str, tuple[str, ...]] = {}
    for t in items:
        seen: list[str] = []
        stack = list(direct.get(t.item_id, []))
        while stack:
            nxt = stack.pop(0)
            if nxt in seen or nxt == t.item_id:
                continue
            seen.append(nxt)
            stack.extend(direct.get(nxt, []))
        out[t.item_id] = tuple(sorted(seen))
    return out


def next_actions(tasks: Iterable[SubTask]) -> list[NextAction]:
    """Open, not-blocked sub-issues that unblock others, the most unblocking first."""
    items = list(tasks)
    deps = dependents_of(items)
    candidates = [t for t in items if t.status not in CLOSED and t.status != "blocked" and deps.get(t.item_id)]
    candidates.sort(key=lambda t: (-len(deps[t.item_id]), t.position, t.item_id))
    return [NextAction(t.item_id, deps[t.item_id]) for t in candidates]
