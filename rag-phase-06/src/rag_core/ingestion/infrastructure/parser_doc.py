"""Legacy .doc adapter: convert to DOCX with LibreOffice headless, then parse."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from rag_core.ingestion.domain.errors import MissingLibreOfficeError, ParseFailedError
from rag_core.ingestion.domain.model import ContentBlock
from rag_core.ingestion.infrastructure.parser_docx import parse_docx

SOFFICE_CANDIDATES = ("soffice", "libreoffice")
CONVERT_TIMEOUT_S = 120


def find_soffice() -> Path | None:
    for name in SOFFICE_CANDIDATES:
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


def convert_doc_to_docx(source: Path, dest_dir: Path, soffice: Path | None = None) -> Path:
    binary = soffice or find_soffice()
    if binary is None:
        raise MissingLibreOfficeError(str(source))
    dest_dir.mkdir(parents=True, exist_ok=True)
    command = [
        str(binary),
        "--headless",
        "--norestore",
        "--convert-to",
        "docx",
        "--outdir",
        str(dest_dir),
        str(source),
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=CONVERT_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as exc:
        raise ParseFailedError(str(source), f"LibreOffice conversion timed out after {CONVERT_TIMEOUT_S}s") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip() or f"exit {completed.returncode}"
        raise ParseFailedError(str(source), f"LibreOffice conversion failed: {detail}")
    produced = dest_dir / (source.stem + ".docx")
    if not produced.is_file():
        # LibreOffice sometimes changes the stem; accept the only docx in the folder.
        matches = list(dest_dir.glob("*.docx"))
        if len(matches) == 1:
            produced = matches[0]
        else:
            raise ParseFailedError(str(source), "LibreOffice did not write a .docx output")
    return produced


def parse_doc(path: Path, soffice: Path | None = None) -> tuple[list[ContentBlock], Path]:
    """Convert ``path`` and parse the DOCX. Returns (blocks, converted_docx_path)."""
    if find_soffice() is None and soffice is None:
        raise MissingLibreOfficeError(str(path))
    tmp = Path(tempfile.mkdtemp(prefix="rag-doc-"))
    converted = convert_doc_to_docx(path, tmp, soffice=soffice)
    return parse_docx(converted), converted
