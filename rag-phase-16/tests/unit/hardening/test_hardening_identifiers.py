"""Phase 15 hardening: identifier value objects, layer index, language and errors (shared kernel)."""

import pytest

from rag_core.shared_kernel.confidentiality import Confidentiality
from rag_core.shared_kernel.errors import DomainError, InvariantError, NotFoundError
from rag_core.shared_kernel.identifiers import (
    DocumentId,
    ExecutorId,
    IssueId,
    KnowledgeItemId,
    NodeIdentifier,
    ProjectId,
    RfpId,
)
from rag_core.shared_kernel.language import LanguageCode
from rag_core.shared_kernel.layer import LayerIndex

pytestmark = [pytest.mark.hardening, pytest.mark.shared_kernel]


def test_node_identifier_strips_whitespace() -> None:
    node = NodeIdentifier("  N-SW-WEB ")
    assert node.value == "N-SW-WEB" and str(node) == "N-SW-WEB"


@pytest.mark.parametrize("value", ["n-sw-web", "SW-WEB", "N--X"])
def test_node_identifier_rejects(value: str) -> None:
    with pytest.raises(InvariantError, match="NodeIdentifier"):
        NodeIdentifier(value)


def test_document_id_normalizes_digits_and_case() -> None:
    assert DocumentId(" ar-fin-۰۰۸ ").value == "AR-FIN-008"
    assert DocumentId("AR-CNT-1402-118").value == "AR-CNT-1402-118"


@pytest.mark.parametrize("value", ["AR-FINANCE-001", "AR-FIN-1"])
def test_document_id_rejects(value: str) -> None:
    with pytest.raises(InvariantError, match="DocumentId"):
        DocumentId(value)


def test_sub_issue_id_parts() -> None:
    sub = IssueId("ar-iss-024/win")
    assert sub.value == "AR-ISS-024/WIN" and sub.is_subissue and sub.suffix == "WIN"
    assert sub.parent_id == IssueId("AR-ISS-024")


def test_top_level_issue_id_parts() -> None:
    top = IssueId("AR-ISS-۰۲۴")
    assert top.value == "AR-ISS-024" and not top.is_subissue
    assert top.parent_id is None and top.suffix is None


@pytest.mark.parametrize("value", ["AR-ISS-24", "AR-ISS-024/"])
def test_issue_id_rejects(value: str) -> None:
    with pytest.raises(InvariantError, match="IssueId"):
        IssueId(value)


def test_executor_and_project_ids_are_normalized() -> None:
    assert ExecutorId(" ex roozbeh mohseni ").value == "EX-ROOZBEH-MOHSENI"
    assert ProjectId("prj-web-۲").value == "PRJ-WEB-2"


def test_rfp_id() -> None:
    assert RfpId("ar-rfp-۱۴۰۳-۰۷").value == "AR-RFP-1403-07"
    with pytest.raises(InvariantError, match="RfpId"):
        RfpId("AR-RFP-1403-7")


def test_knowledge_item_id_prefers_document_shape() -> None:
    item = KnowledgeItemId("ar-fin-008")
    assert item.value == "AR-FIN-008" and item.as_document_id() == DocumentId(
        "AR-FIN-008"
    )
    assert KnowledgeItemId("KI-ALPHA.1").value == "KI-ALPHA.1"


def test_knowledge_item_id_rejects_lowercase_free_text() -> None:
    with pytest.raises(InvariantError, match="KnowledgeItemId"):
        KnowledgeItemId("chunk_x")


def test_identifiers_sort_by_value() -> None:
    docs = sorted([DocumentId("AR-HR-005"), DocumentId("AR-FIN-008")])
    assert [d.value for d in docs] == ["AR-FIN-008", "AR-HR-005"]


@pytest.mark.parametrize("value", [True, 10, -1, "1"])
def test_layer_index_rejects(value: object) -> None:
    with pytest.raises(InvariantError, match="LayerIndex"):
        LayerIndex(value)  # type: ignore[arg-type]


def test_layer_index_code_and_adjacency() -> None:
    assert LayerIndex(2).code == "L2" and str(LayerIndex(2)) == "L2"
    assert LayerIndex(2).is_adjacent_parent_of(LayerIndex(3))
    assert not LayerIndex(1).is_adjacent_parent_of(LayerIndex(3))


@pytest.mark.parametrize(
    ("value", "code"), [(" Farsi ", LanguageCode.FA), ("ENG", LanguageCode.EN)]
)
def test_language_aliases(value: str, code: LanguageCode) -> None:
    assert LanguageCode.parse(value) is code


@pytest.mark.parametrize("value", ["de", None])
def test_language_rejects(value: object) -> None:
    with pytest.raises(InvariantError, match="unsupported language"):
        LanguageCode.parse(value)  # type: ignore[arg-type]


def test_confidentiality_values_and_error_hierarchy() -> None:
    assert {c.value for c in Confidentiality} == {
        "restricted",
        "internal",
        "per_item",
        "public",
    }
    assert issubclass(InvariantError, DomainError) and issubclass(
        NotFoundError, DomainError
    )
