"""Domain services: duplicate/overlap classification and citation value object."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from rag_core.knowledge.domain.model import KnowledgeItem, KnowledgeVersion
from rag_core.shared_kernel.identifiers import DocumentId
from rag_core.shared_kernel.language import LanguageCode


@dataclass(frozen=True)
class Citation:
    """Pointer from an answer or package back to a chunk or section."""

    document_id: DocumentId
    version: str
    language: LanguageCode
    chunk_id: str = ""
    section: str = ""
    heading_path: str = ""

    def __post_init__(self) -> None:
        if not (self.chunk_id or self.section or self.heading_path):
            # A document-level citation is still valid (L0 citation granularity).
            pass

    def __str__(self) -> str:
        loc = self.chunk_id or self.section or self.heading_path
        return f"{self.document_id}@{self.version}" + (f"#{loc}" if loc else "")


class DuplicateKind(StrEnum):
    EXACT = "exact"
    NEAR = "near"
    OVERLAP = "overlap"
    CROSS_LANGUAGE_PAIR = "cross_language_pair"
    DISTINCT = "distinct"


@dataclass(frozen=True)
class DuplicateVerdict:
    kind: DuplicateKind
    reason: str


class DuplicateDetector:
    """Compare two versions or items. FA/EN of the same id is never a duplicate."""

    def classify_items(self, left: KnowledgeItem, right: KnowledgeItem) -> DuplicateVerdict:
        if left.document_id == right.document_id and left is not right:
            return DuplicateVerdict(
                DuplicateKind.CROSS_LANGUAGE_PAIR
                if {v.language for v in left.versions} != {v.language for v in right.versions}
                else DuplicateKind.EXACT,
                "same document id",
            )
        # Compare each active version pair by hash set.
        return self.classify_versions(
            _first_version(left),
            _first_version(right),
            same_document=left.document_id == right.document_id,
        )

    def classify_versions(
        self,
        left: KnowledgeVersion,
        right: KnowledgeVersion,
        *,
        same_document: bool = False,
    ) -> DuplicateVerdict:
        if same_document and left.language != right.language:
            return DuplicateVerdict(
                DuplicateKind.CROSS_LANGUAGE_PAIR,
                "FA/EN pair of the same document id is not a duplicate",
            )
        left_hashes = {c.content_hash for c in left.chunks}
        right_hashes = {c.content_hash for c in right.chunks}
        if left_hashes and left_hashes == right_hashes:
            return DuplicateVerdict(DuplicateKind.EXACT, "identical chunk hashes")
        shared = left_hashes & right_hashes
        if shared and (shared != left_hashes or shared != right_hashes):
            return DuplicateVerdict(DuplicateKind.OVERLAP, "shared chunk hashes")
        if shared and left_hashes != right_hashes:
            return DuplicateVerdict(DuplicateKind.OVERLAP, "shared chunk hashes")
        return DuplicateVerdict(DuplicateKind.DISTINCT, "no shared hashes")


def _first_version(item: KnowledgeItem) -> KnowledgeVersion:
    if not item.versions:
        raise LookupError("item has no versions")
    return item.versions[0]
