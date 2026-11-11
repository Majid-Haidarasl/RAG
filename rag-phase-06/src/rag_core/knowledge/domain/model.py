"""KnowledgeItem aggregate: versions, chunk lifecycle, metadata, source references.

Phase 5 adds the lifecycle:

* Version states: ``draft`` → ``active`` → ``superseded`` → ``archived``
  (a draft can also be discarded straight to ``archived``).
* Effective dates and a ``supersedes`` chain per language.
* Chunk states tied to their version: ``active`` → ``stale`` (a draft that
  will replace this version exists) → ``retired`` (version no longer active).
* Re-ingest by file SHA-256: unchanged file = no new version; changed file =
  new minor version, old chunks retired.

Phase 3 compatibility: ``VersionStatus.INACTIVE`` is an alias of
``SUPERSEDED`` and ``add_version`` still activates immediately.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from enum import StrEnum
from hashlib import sha256

from rag_core.knowledge.domain.fingerprint import normalized_hash
from rag_core.shared_kernel.confidentiality import Confidentiality
from rag_core.shared_kernel.errors import InvariantError, NotFoundError
from rag_core.shared_kernel.events import DomainEvent
from rag_core.shared_kernel.identifiers import DocumentId, KnowledgeItemId, NodeIdentifier
from rag_core.shared_kernel.language import LanguageCode
from rag_core.shared_kernel.numerals import normalize_digits


class VersionStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"
    INACTIVE = "superseded"  # Phase 3 name, alias of SUPERSEDED


class ChunkStatus(StrEnum):
    ACTIVE = "active"
    STALE = "stale"
    RETIRED = "retired"


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
    """Retrievable part of a version. Identity is chunk_id within the version.

    ``content_hash`` hashes the stored text byte-for-byte; ``normalized_hash``
    hashes the canonical form used by exact-duplicate detection.
    """

    chunk_id: str
    order: int
    text: str
    heading_path: str = ""
    section: str = ""
    content_hash: str = ""
    normalized_hash: str = ""
    status: ChunkStatus = ChunkStatus.ACTIVE

    def __post_init__(self) -> None:
        if not self.chunk_id:
            raise InvariantError("chunk_id is required")
        if self.order < 0:
            raise InvariantError("chunk order must be >= 0")
        if not self.content_hash:
            digest = sha256(self.text.encode("utf-8")).hexdigest()
            object.__setattr__(self, "content_hash", digest)
        if not self.normalized_hash:
            object.__setattr__(self, "normalized_hash", normalized_hash(self.text))

    def with_status(self, status: ChunkStatus) -> KnowledgeChunk:
        return replace(self, status=status)


@dataclass
class KnowledgeVersion:
    tag: VersionTag
    language: LanguageCode
    status: VersionStatus
    chunks: list[KnowledgeChunk] = field(default_factory=list)
    file_sha256: str = ""
    effective_from: date | None = None
    effective_to: date | None = None
    supersedes: VersionTag | None = None

    def chunk_by_id(self, chunk_id: str) -> KnowledgeChunk:
        for chunk in self.chunks:
            if chunk.chunk_id == chunk_id:
                return chunk
        raise NotFoundError(f"unknown chunk {chunk_id}")

    def qualified_chunk_id(self, document_id: DocumentId, chunk: KnowledgeChunk) -> str:
        return f"{document_id}@{self.tag}/{self.language.value}#{chunk.chunk_id.split('#')[-1]}"

    def _set_chunk_status(self, status: ChunkStatus, *, only: ChunkStatus | None = None) -> int:
        changed = 0
        updated: list[KnowledgeChunk] = []
        for chunk in self.chunks:
            if chunk.status != status and (only is None or chunk.status == only):
                updated.append(chunk.with_status(status))
                changed += 1
            else:
                updated.append(chunk)
        self.chunks = updated
        return changed

    def count(self, status: ChunkStatus) -> int:
        return sum(1 for c in self.chunks if c.status == status)


@dataclass
class KnowledgeItem:
    """Aggregate root for one controlled knowledge source (one document id).

    A FA/EN pair is one item with two language versions that may share a
    VersionTag. They are a cross-language pair, not a duplicate.

    Invariants (per language): at most one ACTIVE and one DRAFT version;
    tags strictly increase; a new version ``supersedes`` the previous active
    one; chunks of SUPERSEDED/ARCHIVED versions are RETIRED; chunks of the
    active version are STALE only while a DRAFT exists.
    """

    item_id: KnowledgeItemId
    document_id: DocumentId
    owning_node: NodeIdentifier
    confidentiality: Confidentiality
    scope: KnowledgeScope
    versions: list[KnowledgeVersion] = field(default_factory=list)
    events: list[DomainEvent] = field(default_factory=list)

    # ------------------------------------------------------------ creation
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
        file_sha256: str = "",
        effective_from: date | None = None,
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
        item.events.append(
            DomainEvent("KnowledgeItemRegistered", {"document_id": str(document_id)})
        )
        item.add_version(version, language, chunks, file_sha256=file_sha256, effective_from=effective_from)
        return item

    # ------------------------------------------------------------ queries
    def versions_for(self, language: LanguageCode) -> list[KnowledgeVersion]:
        return sorted((v for v in self.versions if v.language == language), key=lambda v: v.tag)

    def active_version(self, language: LanguageCode) -> KnowledgeVersion:
        for version in self.versions:
            if version.language == language and version.status == VersionStatus.ACTIVE:
                return version
        raise NotFoundError(f"no active {language} version for {self.document_id}")

    def find_active(self, language: LanguageCode) -> KnowledgeVersion | None:
        try:
            return self.active_version(language)
        except NotFoundError:
            return None

    def draft_version(self, language: LanguageCode) -> KnowledgeVersion | None:
        for version in self.versions:
            if version.language == language and version.status == VersionStatus.DRAFT:
                return version
        return None

    def get_version(self, tag: VersionTag, language: LanguageCode) -> KnowledgeVersion:
        for version in self.versions:
            if version.tag == tag and version.language == language:
                return version
        raise NotFoundError(f"{self.document_id}@{tag}/{language}")

    def supersedes_chain(self, language: LanguageCode) -> list[VersionTag]:
        """Newest → oldest following ``supersedes`` links from the latest version."""
        versions = {v.tag: v for v in self.versions if v.language == language}
        if not versions:
            return []
        current: KnowledgeVersion | None = versions[max(versions)]
        chain: list[VersionTag] = []
        while current is not None:
            chain.append(current.tag)
            current = versions.get(current.supersedes) if current.supersedes else None
        return chain

    def latest_tag(self, language: LanguageCode) -> VersionTag | None:
        tags = [v.tag for v in self.versions if v.language == language]
        return max(tags) if tags else None

    # ------------------------------------------------------------ commands
    def add_version(
        self,
        version: VersionTag,
        language: LanguageCode,
        chunks: list[KnowledgeChunk],
        *,
        file_sha256: str = "",
        effective_from: date | None = None,
    ) -> KnowledgeVersion:
        """Create and immediately activate a version (Phase 3 behaviour)."""
        self.stage_draft(version, language, chunks, file_sha256=file_sha256)
        return self.activate(version, language, effective_from=effective_from)

    def stage_draft(
        self,
        version: VersionTag,
        language: LanguageCode,
        chunks: list[KnowledgeChunk],
        *,
        file_sha256: str = "",
    ) -> KnowledgeVersion:
        self._assert_chunks(chunks)
        if any(v.tag == version and v.language == language for v in self.versions):
            raise InvariantError(f"version {version} already exists for {language}")
        latest = self.latest_tag(language)
        if latest is not None and version <= latest:
            raise InvariantError(f"version {version} must be greater than {latest}")
        if self.draft_version(language) is not None:
            raise InvariantError(f"a draft already exists for {language}")
        active = self.find_active(language)
        draft = KnowledgeVersion(
            tag=version,
            language=language,
            status=VersionStatus.DRAFT,
            chunks=[c.with_status(ChunkStatus.ACTIVE) for c in chunks],
            file_sha256=file_sha256,
            supersedes=active.tag if active else latest,
        )
        self.versions.append(draft)
        self.events.append(self._event("KnowledgeVersionDrafted", draft))
        if active is not None:
            stale = active._set_chunk_status(ChunkStatus.STALE, only=ChunkStatus.ACTIVE)
            if stale:
                self.events.append(self._event("ChunksMarkedStale", active, count=stale))
        return draft

    def activate(
        self,
        version: VersionTag,
        language: LanguageCode,
        *,
        effective_from: date | None = None,
    ) -> KnowledgeVersion:
        draft = self.get_version(version, language)
        if draft.status is not VersionStatus.DRAFT:
            raise InvariantError(f"only a draft can be activated, {version} is {draft.status}")
        on = effective_from or date.today()
        previous = self.find_active(language)
        if previous is not None:
            if previous.effective_from and on < previous.effective_from:
                raise InvariantError("effective_from cannot precede the version it supersedes")
            previous.status = VersionStatus.SUPERSEDED
            previous.effective_to = on
            retired = previous._set_chunk_status(ChunkStatus.RETIRED)
            self.events.append(self._event("KnowledgeVersionSuperseded", previous, by=str(version)))
            if retired:
                self.events.append(self._event("ChunksRetired", previous, count=retired))
        draft.status = VersionStatus.ACTIVE
        draft.effective_from = on
        self.events.append(self._event("KnowledgeVersionActivated", draft))
        return draft

    def discard_draft(self, language: LanguageCode) -> KnowledgeVersion:
        draft = self.draft_version(language)
        if draft is None:
            raise InvariantError(f"no draft to discard for {language}")
        draft.status = VersionStatus.ARCHIVED
        draft._set_chunk_status(ChunkStatus.RETIRED)
        active = self.find_active(language)
        if active is not None:
            active._set_chunk_status(ChunkStatus.ACTIVE, only=ChunkStatus.STALE)
        self.events.append(self._event("KnowledgeVersionArchived", draft, reason="draft discarded"))
        return draft

    def archive(self, version: VersionTag, language: LanguageCode) -> KnowledgeVersion:
        target = self.get_version(version, language)
        if target.status is VersionStatus.ACTIVE:
            raise InvariantError("an active version cannot be archived; withdraw or supersede it first")
        if target.status is VersionStatus.DRAFT:
            return self.discard_draft(language)
        if target.status is VersionStatus.ARCHIVED:
            raise InvariantError(f"{version} is already archived")
        target.status = VersionStatus.ARCHIVED
        self.events.append(self._event("KnowledgeVersionArchived", target))
        return target

    def withdraw(self, language: LanguageCode, *, on: date | None = None) -> KnowledgeVersion:
        """Take the active version out of use without a replacement."""
        active = self.active_version(language)
        active.status = VersionStatus.ARCHIVED
        active.effective_to = on or date.today()
        retired = active._set_chunk_status(ChunkStatus.RETIRED)
        self.events.append(self._event("KnowledgeVersionArchived", active, reason="withdrawn"))
        if retired:
            self.events.append(self._event("ChunksRetired", active, count=retired))
        return active

    def reingest(
        self,
        language: LanguageCode,
        file_sha256: str,
        chunks: list[KnowledgeChunk],
        *,
        effective_from: date | None = None,
    ) -> KnowledgeVersion | None:
        """Re-ingest a file. Same SHA-256 as the active version → None (no-op).

        A changed file creates and activates the next minor version; the
        previous version's chunks are retired.
        """
        if not file_sha256:
            raise InvariantError("re-ingest requires the file sha256")
        active = self.find_active(language)
        if active is not None and active.file_sha256 == file_sha256:
            self.events.append(self._event("ReingestSkippedUnchanged", active))
            return None
        latest = self.latest_tag(language)
        tag = latest.bump_minor() if latest else VersionTag(1, 0)
        return self.add_version(tag, language, chunks, file_sha256=file_sha256, effective_from=effective_from)

    def active_chunks(self, language: LanguageCode | None = None) -> list[KnowledgeChunk]:
        """Chunks the retriever may use (ACTIVE or STALE of an active version)."""
        out: list[KnowledgeChunk] = []
        for version in self.versions:
            if version.status is not VersionStatus.ACTIVE:
                continue
            if language is not None and version.language != language:
                continue
            out.extend(c for c in version.chunks if c.status is not ChunkStatus.RETIRED)
        return out

    # ------------------------------------------------------------ helpers
    def _event(self, name: str, version: KnowledgeVersion, **extra: object) -> DomainEvent:
        payload: dict[str, object] = {
            "document_id": str(self.document_id),
            "version": str(version.tag),
            "language": version.language.value,
        }
        payload.update(extra)
        return DomainEvent(name, payload)

    def _assert_chunks(self, chunks: list[KnowledgeChunk]) -> None:
        if not chunks:
            raise InvariantError("a version needs at least one chunk")
        ids = [c.chunk_id for c in chunks]
        if len(ids) != len(set(ids)):
            raise InvariantError("chunk ids must be unique within a version")
        orders = [c.order for c in chunks]
        if orders != sorted(orders):
            raise InvariantError("chunks must be supplied in non-decreasing order")
