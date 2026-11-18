from pathlib import Path

import pytest

from rag_core.ingestion.application.metadata import load_schema, validate_metadata
from rag_core.ingestion.application.pipeline import ingest_file
from rag_core.ingestion.domain.errors import UnsupportedFormatError
from rag_core.ingestion.infrastructure.dispatcher import CompositeDocumentParser
from tests.fixtures.ingestion.builders import write_sample_docx, write_scanned_pdf

pytestmark = pytest.mark.ingestion

REPO = Path(__file__).resolve().parents[3]


def test_pipeline_normalizes_ids_and_arabic_letters(tmp_path: Path) -> None:
    path = write_sample_docx(tmp_path / "fa" / "AR-HR-005-leave.docx")
    doc = ingest_file(path, repo_root=REPO)
    assert doc.document_id == "AR-HR-005"
    assert "AR-HR-005" in doc.text
    assert "AR-HR-۰۰۵" not in doc.text
    assert "آزمایشی" in doc.text or "حرف" in doc.text
    assert "ي" not in doc.text and "ك" not in doc.text
    assert doc.normalization.id_digits >= 1
    assert doc.chunks
    assert doc.metadata["owning_node"] == "N-ADM-HR"
    assert doc.metadata["language"] == "fa"
    assert doc.metadata["bilingual_pair"] is None or doc.metadata["bilingual_pair"]["language"] == "en"
    validate_metadata(doc.metadata, repo_root=REPO)
    # Source anchors present for Phase 8
    assert doc.chunks[0].anchors[0].document_id == "AR-HR-005"


def test_schema_rejects_persian_digits_in_id() -> None:
    schema = load_schema(REPO)
    assert schema["properties"]["id"]["pattern"].startswith("^AR-")
    with pytest.raises(Exception):
        validate_metadata(
            {
                "id": "AR-FIN-۰۰۸",
                "language": "fa",
                "owning_node": "N-ADM-FIN",
                "doc_type": "financial_report",
                "version": "1.0",
                "file_name": "x.docx",
                "file_sha256": "a" * 64,
                "file_format": "docx",
                "byte_size": 1,
                "is_scanned": False,
                "ingested_at": "2026-11-10T00:00:00Z",
            },
            repo_root=REPO,
        )


def test_unsupported_format_is_clear(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("hello", encoding="utf-8")
    with pytest.raises(UnsupportedFormatError, match="unsupported document format"):
        CompositeDocumentParser().parse(path)


def test_scanned_pdf_is_flagged_in_pipeline(tmp_path: Path) -> None:
    path = write_scanned_pdf(tmp_path / "en" / "AR-SW-022-scan.pdf")
    doc = ingest_file(path, repo_root=REPO)
    assert doc.is_scanned is True
    assert doc.scanned_pages == (1,)
    assert any("LVM OCR" in w for w in doc.warnings)
    assert doc.metadata["is_scanned"] is True
