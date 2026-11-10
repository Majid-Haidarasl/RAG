"""KnowledgeItem aggregate: versions, chunks, metadata, source references."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from hashlib import sha256

from rag_core.shared_kernel.confidentiality import Confidentiality
from rag_core.shared_kernel.errors import InvariantError, NotFoundError
from rag_core.shared_kernel.events import DomainEvent
from rag_core.shared_kernel.identifiers import DocumentId, KnowledgeItemId, NodeIdentifier
from rag_core.shared_kernel.language import LanguageCode
from rag_core.shared_kernel.numerals import normalize_digits


class VersionStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


@dataclass(frozen=True, order=True)
class VersionTag:
    """Immutable version label ``major.minor``, e.g. 1.0 or 1.1."""

    major: int
    minor: int

    def __post_init__(self) -> None:
        if self.major < 0 or self.minor < 0:
            raise InvariantError("VersionTag parts must be >= 0")

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}"

    @classmethod
    def parse(cls, text: str) -> VersionTag:
        raw = normalize_digits(text.strip())
        parts = raw.split(".")
        if len(parts) != 2 or not all(p.isdigit() for p in parts):
            raise InvariantError(f"invalid VersionTag: {text!r}")
        return cls(int(parts[0]), int(parts[1]))

    def bump_minor(self) -> VersionTag:
        return VersionTag(self.major, self.minor + 1)


@dataclass(frozen=True)
class SourceReference:
    document_id: DocumentId
    version: VersionTag
    section: str = ""
    heading_path: str = ""
    chunk_id: str = ""
    page: str = ""

    def __str__(self) -> str:
        loc = self.chunk_id or self.section or self.heading_path
        suffix = f", {loc}" if loc else ""
        return f"{self.document_id}@{self.version}{suffix}"


@dataclass(frozen=True)
class KnowledgeScope:
    subject_domain: str
    confidentiality: Confidentiality
    usage: str = "retrieval"


@dataclass(frozen=True)
class KnowledgeChunk:
    """Retrievable part of a version. Identity is chunk_id within the version."""

    chunk_id: str
    order: int
    text: str
    heading_path: str = ""
    section: str = ""
    content_hash: str = ""

    def __post_init__(self) -> None:
        if not self.chunk_id:
            raise InvariantError("chunk_id is required")
        if self.order < 0:
            raise InvariantError("chunk order must be >= 0")
        if not self.content_hash:
            digest = sha256(self.text.encode("utf-8")).hexdigest()
            object.__setattr__(self, "content_hash", digest)


@dataclass
class KnowledgeVersion:
    tag: VersionTag
    language: LanguageCode
    status: VersionStatus
    chunks: list[KnowledgeChunk] = field(default_factory=list)

    def chunk_by_id(self, chunk_id: str) -> KnowledgeChunk:
        for chunk in self.chunks:
            if chunk.chunk_id == chunk_id:
                return chunk
        raise NotFoundError(f"unknown chunk {chunk_id}")


@dataclass
class KnowledgeItem:
    """Aggregate root for one controlled knowledge source (one document id).

    A FA/EN pair is one item with two language versions that may share a
    VersionTag. They are a cross-language pair, not a duplicate.
    """

    item_id: KnowledgeItemId
    document_id: DocumentId
    owning_node: NodeIdentifier
    confidentiality: Confidentiality
    scope: KnowledgeScope
    versions: list[KnowledgeVersion] = field(default_factory=list)
    events: list[DomainEvent] = field(default_factory=list)

    @classmethod
    def register(
        cls,
        *,
        document_id: DocumentId,
        owning_node: NodeIdentifier,
        confidentiality: Confidentiality,
        subject_domain: str,
        language: LanguageCode,
        version: VersionTag,
        chunks: list[KnowledgeChunk],
    ) -> KnowledgeItem:
        if not subject_domain.strip():
            raise InvariantError("KnowledgeItem requires a subject domain")
        item = cls(
            item_id=KnowledgeItemId(str(document_id)),
            document_id=document_id,
            owning_node=owning_node,
            confidentiality=confidentiality,
            scope=KnowledgeScope(subject_domain, confidentiality),
        )
        item._add_version(version, language, chunks, first=True)
        item.events.append(
            DomainEvent("KnowledgeItemRegistered", {"document_id": str(document_id)})
        )
        return item

    def add_version(
        self,
        version: VersionTag,
        language: LanguageCode,
        chunks: list[KnowledgeChunk],
    ) -> KnowledgeVersion:
        added = self._add_version(version, language, chunks, first=False)
        self.events.append(
            DomainEvent(
                "KnowledgeVersionActivated",
                {"document_id": str(self.document_id), "version": str(version), "language": language.value},
            )
        )
        return added

    def active_version(self, language: LanguageCode) -> KnowledgeVersion:
        for version in self.versions:
            if version.language == language and version.status == VersionStatus.ACTIVE:
                return version
        raise NotFoundError(f"no active {language} version for {self.document_id}")

    def _add_version(
        self,
        version: VersionTag,
        language: LanguageCode,
        chunks: list[KnowledgeChunk],
        *,
        first: bool,
    ) -> KnowledgeVersion:
        self._assert_chunks(chunks)
        if any(v.tag == version and v.language == language for v in self.versions):
            raise InvariantError(f"version {version} already exists for {language}")
        if not first:
            for existing in self.versions:
                if existing.language == language and existing.status == VersionStatus.ACTIVE:
                    existing.status = VersionStatus.INACTIVE
        added = KnowledgeVersion(
            tag=version,
            language=language,
            status=VersionStatus.ACTIVE,
            chunks=list(chunks),
        )
        self.versions.append(added)
        return added

    def _assert_chunks(self, chunks: list[KnowledgeChunk]) -> None:
        if not chunks:
            raise InvariantError("a version needs at least one chunk")
        ids = [c.chunk_id for c in chunks]
        if len(ids) != len(set(ids)):
            raise InvariantError("chunk ids must be unique within a version")
        orders = [c.order for c in chunks]
        if orders != sorted(orders):
            raise InvariantError("chunks must be supplied in non-decreasing order")
