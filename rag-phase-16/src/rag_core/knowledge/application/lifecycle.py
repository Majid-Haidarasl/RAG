"""Application service: map ingestion output onto the KnowledgeItem lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from rag_core.ingestion.domain.catalog import lookup
from rag_core.ingestion.domain.model import IngestedDocument
from rag_core.knowledge.domain.model import KnowledgeChunk, KnowledgeItem, KnowledgeVersion, VersionTag
from rag_core.knowledge.infrastructure.memory import InMemoryKnowledgeItemRepository
from rag_core.shared_kernel.confidentiality import Confidentiality
from rag_core.shared_kernel.identifiers import DocumentId, NodeIdentifier
from rag_core.shared_kernel.language import LanguageCode


@dataclass(frozen=True)
class LifecycleOutcome:
    document_id: str
    language: str
    action: str  # registered | added_language | new_version | unchanged
    version: str


def to_domain_chunks(doc: IngestedDocument) -> list[KnowledgeChunk]:
    return [
        KnowledgeChunk(
            chunk_id=chunk.chunk_id,
            order=chunk.order,
            text=chunk.text,
            heading_path=chunk.heading_path,
        )
        for chunk in doc.chunks
    ]


class KnowledgeLifecycleService:
    def __init__(self, repository: InMemoryKnowledgeItemRepository | None = None) -> None:
        self.repository = repository or InMemoryKnowledgeItemRepository()

    def ingest(self, doc: IngestedDocument, *, effective_from: date | None = None) -> LifecycleOutcome:
        if doc.language is None:
            raise ValueError(f"{doc.path}: language is required for the lifecycle")
        document_id = DocumentId(doc.document_id)
        chunks = to_domain_chunks(doc)
        item = self.repository.find_by_document(document_id)
        entry = lookup(doc.document_id)
        start_tag = VersionTag.parse(entry.version) if entry else VersionTag(1, 0)
        if item is None:
            item = KnowledgeItem.register(
                document_id=document_id,
                owning_node=NodeIdentifier(entry.owning_node if entry else "N-LIB"),
                confidentiality=Confidentiality(entry.confidentiality if entry else "internal"),
                subject_domain=entry.doc_type if entry else "unknown",
                language=doc.language,
                version=start_tag,
                chunks=chunks,
                file_sha256=doc.file_sha256,
                effective_from=effective_from,
            )
            self.repository.save(item)
            return LifecycleOutcome(doc.document_id, doc.language.value, "registered", str(start_tag))
        if item.latest_tag(doc.language) is None:
            version = item.add_version(
                start_tag, doc.language, chunks, file_sha256=doc.file_sha256, effective_from=effective_from
            )
            self.repository.save(item)
            return LifecycleOutcome(doc.document_id, doc.language.value, "added_language", str(version.tag))
        result: KnowledgeVersion | None = item.reingest(
            doc.language, doc.file_sha256, chunks, effective_from=effective_from
        )
        self.repository.save(item)
        if result is None:
            active = item.active_version(doc.language)
            return LifecycleOutcome(doc.document_id, doc.language.value, "unchanged", str(active.tag))
        return LifecycleOutcome(doc.document_id, doc.language.value, "new_version", str(result.tag))

    def items(self) -> list[KnowledgeItem]:
        return self.repository.all()

    @staticmethod
    def language_of(value: str) -> LanguageCode:
        return LanguageCode.parse(value)
