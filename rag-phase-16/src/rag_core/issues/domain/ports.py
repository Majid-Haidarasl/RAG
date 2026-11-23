"""Ports of the Issue Management context.

The issues context never imports the hierarchy aggregate. It asks an
``OrgDirectory`` (anti-corruption layer, implemented in
``issues.infrastructure.hierarchy_acl``) for the facts it needs.
Optional model-backed ports (embeddings, LLM decomposition) are declared here
but no adapter is wired in Phase 7 and tests never call Ollama.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:  # pragma: no cover
    from rag_core.issues.domain.decomposition import SubIssueDraft
    from rag_core.issues.domain.model import Issue


@dataclass(frozen=True)
class OrgNodeView:
    """What the issues context knows about a node (translated by the ACL)."""

    node_id: str
    layer: int
    depth: int
    path: tuple[str, ...]
    is_active: bool = True


@dataclass(frozen=True)
class OrgRoute:
    action: str  # "answer" | "escalate"
    target: str
    reason: str


class OrgDirectory(Protocol):
    def exists(self, node_id: str) -> bool: ...
    def node(self, node_id: str) -> OrgNodeView: ...
    def lowest_common_ancestor(self, node_ids: list[str]) -> str: ...
    def route(self, asking: str, evidence_owners: list[str], *, reserved_decision: bool = False) -> OrgRoute: ...


class TextEmbedder(Protocol):
    """Optional semantic similarity (e.g. a local Ollama embedding model later)."""

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class IssueDecomposer(Protocol):
    """Rule-based by default; an LLM-backed adapter may implement the same port."""

    def decompose(self, issue: Issue) -> list[SubIssueDraft]: ...
