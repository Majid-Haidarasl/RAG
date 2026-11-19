import pytest

from rag_core.knowledge.domain.services import Citation
from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.identifiers import DocumentId, NodeIdentifier
from rag_core.shared_kernel.language import LanguageCode
from rag_core.shared_kernel.layer import LayerIndex
from rag_core.transfer.domain.model import (
    PackageStatus,
    TransferDetailLevel,
    TransferPackage,
    TransferRuleSet,
)
from rag_core.transfer.infrastructure.csv_format import package_from_csv, package_to_csv

pytestmark = pytest.mark.transfer


def _citation() -> Citation:
    return Citation(DocumentId("AR-TRN-026"), "1.0", LanguageCode.FA, section="decisions")


def test_l0_package_requires_risks_decisions_and_sources() -> None:
    rules = TransferRuleSet(LayerIndex(0), TransferDetailLevel.EXECUTIVE)
    with pytest.raises(InvariantError, match="missing required fields"):
        TransferPackage.assemble(
            source_node=NodeIdentifier("N-CEO"),
            target_node=NodeIdentifier("N-BRD"),
            rules=rules,
            fields={"risks": "delay penalty"},
            citations=[_citation()],
        )
    package = TransferPackage.assemble(
        source_node=NodeIdentifier("N-CEO"),
        target_node=NodeIdentifier("N-BRD"),
        rules=rules,
        fields={
            "risks": "ریسک جریمه تأخیر",
            "decisions_requested": "تمدید تا ۲۰ مهر",
            "source_references": "AR-TRN-026",
        },
        citations=[_citation()],
    )
    package.accept()
    assert package.status is PackageStatus.ACCEPTED


def test_csv_round_trip_keeps_persian_text() -> None:
    rules = TransferRuleSet(LayerIndex(0), TransferDetailLevel.EXECUTIVE)
    package = TransferPackage.assemble(
        source_node=NodeIdentifier("N-CEO"),
        target_node=NodeIdentifier("N-BRD"),
        rules=rules,
        fields={
            "risks": "ریسک جریمه تأخیر",
            "decisions_requested": "تمدید تا ۲۰ مهر بدون جریمه",
            "source_references": "AR-TRN-026",
        },
        citations=[_citation()],
    )
    package.accept()
    text = package_to_csv(package)
    restored = package_from_csv(text)
    assert restored.fields["risks"] == "ریسک جریمه تأخیر"
    assert restored.fields["decisions_requested"] == "تمدید تا ۲۰ مهر بدون جریمه"
    assert restored.status is PackageStatus.ACCEPTED
    assert restored.source_node.value == "N-CEO"
