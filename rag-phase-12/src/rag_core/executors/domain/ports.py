"""Ports of the Executor Management context.

The executors context never imports the hierarchy aggregate. A
``TeamDirectory`` (implemented by ``executors.infrastructure.hierarchy_acl``)
answers the few questions it needs about nodes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TeamView:
    node_id: str
    name_en: str
    name_fa: str
    layer: int
    parent_id: str | None
    is_active: bool = True


class TeamDirectory(Protocol):
    def exists(self, node_id: str) -> bool: ...
    def team(self, node_id: str) -> TeamView: ...
