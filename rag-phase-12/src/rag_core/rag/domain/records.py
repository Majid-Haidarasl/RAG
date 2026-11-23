"""Index records, source references and metadata filters (Phase 8).

A ``ChunkRecord`` is the read model the retriever works on. It is built from
Phase 4 chunks (text, page/paragraph anchors) and the Phase 5 lifecycle
(version tag, chunk status), plus Phase 6 ownership (owner node, layer).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from rag_core.knowledge.domain.model import ChunkStatus
from rag_core.shared_kernel.errors import InvariantError


def record_key(document_id: str, version: str, language: str, order: int) -> str:
    """Stable key: ``AR-HR-005@1.0/fa#c0012``. FA and EN never collide."""
    return f"{document_id}@{version}/{language}#c{order:04d}"


@dataclass(frozen=True)
class SourceRef:
    """What a citation points at: document, version, language and position."""

    document_id: str
    version: str
    language: str
    order: int
    heading_path: str = ""
    page: int | None = None
    paragraph: int | None = None
    table: int | None = None

    @property
    def label(self) -> str:
        """Citation label used in prompts and answers, e.g. ``AR-HR-005 §12``."""
        return f"{self.document_id} §{self.order}"

    def describe(self) -> str:
        parts = [f"{self.document_id} v{self.version} ({self.language})", f"§{self.order}"]
        if self.page is not None:
            parts.append(f"p.{self.page}")
        if self.paragraph is not None:
            parts.append(f"¶{self.paragraph}")
        if self.table is not None:
            parts.append(f"table {self.table}")
        if self.heading_path:
            parts.append(self.heading_path)
        return " · ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["label"] = self.label
        return {k: v for k, v in data.items() if v not in (None, "")}


@dataclass(frozen=True)
class ChunkRecord:
    key: str
    document_id: str
    language: str
    version: str
    order: int
    text: str
    heading_path: str = ""
    owner_node: str = ""
    layer: int | None = None
    knowledge_class: str = ""
    confidentiality: str = "internal"
    status: str = ChunkStatus.ACTIVE.value
    version_status: str = "active"
    content_hash: str = ""
    page: int | None = None
    paragraph: int | None = None
    table: int | None = None
    duplicate_of: str = ""  # canonical key of an exact-duplicate group (Phase 5 hash)

    def __post_init__(self) -> None:
        if not self.key or not self.document_id:
            raise InvariantError("ChunkRecord needs key and document_id")
        if self.language not in {"fa", "en"}:
            raise InvariantError(f"unsupported language {self.language!r}")
        if self.status not in {s.value for s in ChunkStatus}:
            raise InvariantError(f"unknown chunk status {self.status!r}")

    @property
    def is_active(self) -> bool:
        return self.status == ChunkStatus.ACTIVE.value and self.version_status == "active"

    @property
    def source(self) -> SourceRef:
        return SourceRef(
            self.document_id, self.version, self.language, self.order,
            self.heading_path, self.page, self.paragraph, self.table,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChunkRecord:
        return cls(**data)


@dataclass(frozen=True)
class SearchFilters:
    """Metadata filters. Empty sets mean "no restriction"."""

    languages: frozenset[str] = field(default_factory=frozenset)
    document_ids: frozenset[str] = field(default_factory=frozenset)
    layers: frozenset[int] = field(default_factory=frozenset)
    knowledge_classes: frozenset[str] = field(default_factory=frozenset)
    active_only: bool = True

    @classmethod
    def of(
        cls,
        *,
        languages: tuple[str, ...] | list[str] = (),
        document_ids: tuple[str, ...] | list[str] = (),
        layers: tuple[int, ...] | list[int] = (),
        knowledge_classes: tuple[str, ...] | list[str] = (),
        active_only: bool = True,
    ) -> SearchFilters:
        return cls(
            frozenset(languages), frozenset(d.upper() for d in document_ids),
            frozenset(layers), frozenset(knowledge_classes), active_only,
        )

    def admits(self, record: ChunkRecord) -> bool:
        if self.active_only and not record.is_active:
            return False
        if self.languages and record.language not in self.languages:
            return False
        if self.document_ids and record.document_id not in self.document_ids:
            return False
        if self.layers and record.layer not in self.layers:
            return False
        if self.knowledge_classes and record.knowledge_class not in self.knowledge_classes:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "languages": sorted(self.languages),
            "document_ids": sorted(self.document_ids),
            "layers": sorted(self.layers),
            "knowledge_classes": sorted(self.knowledge_classes),
            "active_only": self.active_only,
        }
