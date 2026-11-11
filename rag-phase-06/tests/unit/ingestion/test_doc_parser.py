from pathlib import Path

import pytest

from rag_core.ingestion.domain.errors import MissingLibreOfficeError
from rag_core.ingestion.infrastructure.parser_doc import find_soffice, parse_doc
from tests.fixtures.ingestion.builders import write_ordered_docx

pytestmark = pytest.mark.ingestion


def test_missing_soffice_message_tells_the_user_how_to_install(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from rag_core.ingestion.infrastructure import parser_doc as mod

    monkeypatch.setattr(mod, "find_soffice", lambda: None)
    docx = write_ordered_docx(tmp_path / "AR-ORG-001-order.docx")
    # A fake .doc path; conversion is not reached.
    fake = tmp_path / "AR-ORG-001-order.doc"
    fake.write_bytes(docx.read_bytes())
    with pytest.raises(MissingLibreOfficeError, match="sudo apt install -y libreoffice-writer --no-install-recommends"):
        parse_doc(fake)


@pytest.mark.skipif(find_soffice() is None, reason="LibreOffice (soffice) is not installed")
def test_legacy_doc_converts_and_preserves_order(tmp_path: Path) -> None:
    from rag_core.ingestion.infrastructure.parser_doc import convert_doc_to_docx, find_soffice

    source_docx = write_ordered_docx(tmp_path / "AR-ORG-001-order.docx")
    # Create a real .doc via LibreOffice so the adapter has something to convert back.
    soffice = find_soffice()
    assert soffice is not None
    import subprocess

    completed = subprocess.run(
        [
            str(soffice),
            "--headless",
            "--norestore",
            "--convert-to",
            "doc",
            "--outdir",
            str(tmp_path),
            str(source_docx),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    produced = tmp_path / "AR-ORG-001-order.doc"
    if completed.returncode != 0 or not produced.is_file():
        pytest.skip(f"LibreOffice could not write a .doc fixture: {completed.stderr}")
    blocks, converted = parse_doc(produced)
    texts = [b.text for b in blocks]
    assert "BEFORE_TABLE" in texts
    assert "IN_TABLE" in texts
    assert "AFTER_TABLE" in texts
    assert texts.index("BEFORE_TABLE") < texts.index("IN_TABLE") < texts.index("AFTER_TABLE")
    assert converted.suffix == ".docx"
