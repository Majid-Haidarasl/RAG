import pytest

from rag_core.shared_kernel.fact_ports import (
    FactCheckResult,
    FactClaim,
    FactKind,
    FactValidationReport,
    FactVerdict,
)
from rag_core.shared_kernel.identifiers import DocumentId

pytestmark = pytest.mark.shared_kernel


def test_validation_report_all_supported_and_unsupported() -> None:
    ok = FactCheckResult(
        FactClaim(FactKind.DOCUMENT_ID, "AR-FIN-۰۰۸", "AR-FIN-008"),
        FactVerdict.CORRECTED,
        evidence_document_id=DocumentId("AR-FIN-008"),
        replacement="AR-FIN-008",
    )
    bad = FactCheckResult(
        FactClaim(FactKind.PERSON_NAME, "علی محمدی", "علی محمدی"),
        FactVerdict.UNSUPPORTED,
    )
    report = FactValidationReport((ok, bad))
    assert report.all_supported is False
    assert report.unsupported == (bad,)
