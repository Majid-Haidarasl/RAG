import pytest

from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.identifiers import DocumentId, IssueId, NodeIdentifier, ProjectId, RfpId

pytestmark = pytest.mark.shared_kernel


def test_node_identifier_accepts_armanrayan_ids() -> None:
    assert str(NodeIdentifier("N-SW-WEB")) == "N-SW-WEB"
    assert str(NodeIdentifier("N-BRD")) == "N-BRD"


def test_node_identifier_rejects_lowercase_and_spaces() -> None:
    with pytest.raises(InvariantError):
        NodeIdentifier("n-sw-web")
    with pytest.raises(InvariantError):
        NodeIdentifier("SW-WEB")


def test_document_id_normalizes_persian_digits() -> None:
    assert DocumentId("AR-FIN-۰۰۸").value == "AR-FIN-008"


def test_document_id_accepts_contract_and_rfp_shapes() -> None:
    assert DocumentId("AR-CNT-1402-118").value == "AR-CNT-1402-118"
    assert DocumentId("AR-RFP-1403-07").value == "AR-RFP-1403-07"


def test_issue_id_parent_and_suffix() -> None:
    sub = IssueId("AR-ISS-024/WIN")
    assert sub.is_subissue
    assert sub.parent_id == IssueId("AR-ISS-024")
    assert sub.suffix == "WIN"
    assert IssueId("AR-ISS-024").parent_id is None


def test_project_and_rfp_ids() -> None:
    assert str(ProjectId("PRJ-AZP-118")) == "PRJ-AZP-118"
    assert str(RfpId("AR-RFP-1403-07")) == "AR-RFP-1403-07"
