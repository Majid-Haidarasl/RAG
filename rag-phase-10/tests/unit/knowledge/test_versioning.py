import pytest

from rag_core.knowledge.domain.model import (
    KnowledgeChunk,
    KnowledgeItem,
    VersionStatus,
    VersionTag,
)
from rag_core.knowledge.domain.services import DuplicateDetector, DuplicateKind
from rag_core.shared_kernel.confidentiality import Confidentiality
from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.identifiers import DocumentId, NodeIdentifier
from rag_core.shared_kernel.language import LanguageCode

pytestmark = pytest.mark.knowledge


def _chunks(*texts: str) -> list[KnowledgeChunk]:
    return [KnowledgeChunk(chunk_id=f"c{i}", order=i, text=text, heading_path="s") for i, text in enumerate(texts, start=1)]


def _item(doc: str, language: LanguageCode, chunks: list[KnowledgeChunk], node: str = "N-HW-REP") -> KnowledgeItem:
    return KnowledgeItem.register(
        document_id=DocumentId(doc),
        owning_node=NodeIdentifier(node),
        confidentiality=Confidentiality.INTERNAL,
        subject_domain="hardware procedure",
        language=language,
        version=VersionTag.parse("1.0"),
        chunks=chunks,
    )


def test_knowledge_item_without_confidentiality_cannot_be_constructed() -> None:
    # Confidentiality is a required enum argument; an empty subject is rejected.
    with pytest.raises(InvariantError, match="subject"):
        KnowledgeItem.register(
            document_id=DocumentId("AR-HW-012"),
            owning_node=NodeIdentifier("N-HW-REP"),
            confidentiality=Confidentiality.INTERNAL,
            subject_domain="  ",
            language=LanguageCode.FA,
            version=VersionTag.parse("1.0"),
            chunks=_chunks("text"),
        )


def test_updating_creates_v1_1_active_and_keeps_v1_0_inactive() -> None:
    item = _item("AR-HW-012", LanguageCode.FA, _chunks("v1 body"))
    item.add_version(VersionTag.parse("1.1"), LanguageCode.FA, _chunks("v1.1 body"))
    active = item.active_version(LanguageCode.FA)
    assert str(active.tag) == "1.1"
    assert active.status is VersionStatus.ACTIVE
    previous = next(v for v in item.versions if str(v.tag) == "1.0")
    assert previous.status is VersionStatus.INACTIVE


def test_chunks_keep_document_id_version_heading_path_and_order() -> None:
    chunks = [
        KnowledgeChunk("c1", 1, "intro", heading_path="AR-ORG-002 > 1"),
        KnowledgeChunk("c2", 2, "tree", heading_path="AR-ORG-002 > 2"),
    ]
    item = _item("AR-ORG-002", LanguageCode.EN, chunks, node="N-CEO")
    version = item.active_version(LanguageCode.EN)
    assert item.document_id.value == "AR-ORG-002"
    assert str(version.tag) == "1.0"
    assert [c.heading_path for c in version.chunks] == ["AR-ORG-002 > 1", "AR-ORG-002 > 2"]
    assert [c.order for c in version.chunks] == [1, 2]


def test_same_hash_is_exact_duplicate() -> None:
    left = _item("AR-HW-012", LanguageCode.FA, _chunks("same body"))
    right = _item("AR-HW-099", LanguageCode.FA, _chunks("same body"))
    verdict = DuplicateDetector().classify_versions(left.versions[0], right.versions[0])
    assert verdict.kind is DuplicateKind.EXACT


def test_fa_en_pair_of_same_document_is_not_a_duplicate() -> None:
    fa = _item("AR-SW-016", LanguageCode.FA, _chunks("متن فارسی"))
    # Same item also holds the English version.
    fa.add_version(VersionTag.parse("1.0"), LanguageCode.EN, _chunks("English body"))
    verdict = DuplicateDetector().classify_versions(
        fa.active_version(LanguageCode.FA),
        fa.active_version(LanguageCode.EN),
        same_document=True,
    )
    assert verdict.kind is DuplicateKind.CROSS_LANGUAGE_PAIR


def test_shared_chunk_hash_is_overlap_not_exact() -> None:
    left = _item("AR-FIN-008", LanguageCode.FA, _chunks("contract split 2180", "board only"))
    right = _item("AR-ISS-024", LanguageCode.FA, _chunks("contract split 2180", "issue only"), node="N-LIB")
    verdict = DuplicateDetector().classify_versions(left.versions[0], right.versions[0])
    assert verdict.kind is DuplicateKind.OVERLAP
