"""Extra coverage for parser_doc: LibreOffice discovery and conversion edge cases."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import subprocess

import pytest

from rag_core.ingestion.domain.errors import MissingLibreOfficeError, ParseFailedError
from rag_core.ingestion.infrastructure import parser_doc as mod
from rag_core.ingestion.infrastructure.parser_doc import (
    convert_doc_to_docx,
    find_soffice,
    parse_doc,
)
from tests.fixtures.ingestion.builders import write_ordered_docx

pytestmark = pytest.mark.ingestion


def test_find_soffice_returns_first_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        mod.shutil,
        "which",
        lambda name: "/usr/bin/soffice" if name == "soffice" else None,
    )
    assert find_soffice() == Path("/usr/bin/soffice")


def test_find_soffice_falls_back_to_libreoffice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        mod.shutil,
        "which",
        lambda name: "/usr/bin/libreoffice" if name == "libreoffice" else None,
    )
    assert find_soffice() == Path("/usr/bin/libreoffice")


def test_find_soffice_returns_none_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mod.shutil, "which", lambda _name: None)
    assert find_soffice() is None


def test_convert_raises_when_binary_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mod, "find_soffice", lambda: None)
    with pytest.raises(MissingLibreOfficeError):
        convert_doc_to_docx(tmp_path / "x.doc", tmp_path / "out")


def test_convert_timeout_becomes_parse_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mod, "find_soffice", lambda: Path("/fake/soffice"))

    def boom(*_a, **_k):
        raise subprocess.TimeoutExpired(cmd="soffice", timeout=1)

    monkeypatch.setattr(mod.subprocess, "run", boom)
    with pytest.raises(ParseFailedError, match="timed out"):
        convert_doc_to_docx(tmp_path / "x.doc", tmp_path / "out")


def test_convert_nonzero_prefers_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mod, "find_soffice", lambda: Path("/fake/soffice"))
    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *_a, **_k: SimpleNamespace(
            returncode=7, stderr="bad convert\n", stdout="ignored"
        ),
    )
    with pytest.raises(ParseFailedError, match="bad convert"):
        convert_doc_to_docx(tmp_path / "x.doc", tmp_path / "out")


def test_convert_nonzero_falls_back_to_stdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mod, "find_soffice", lambda: Path("/fake/soffice"))
    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *_a, **_k: SimpleNamespace(
            returncode=3, stderr="", stdout="stdout detail"
        ),
    )
    with pytest.raises(ParseFailedError, match="stdout detail"):
        convert_doc_to_docx(tmp_path / "x.doc", tmp_path / "out")


def test_convert_nonzero_falls_back_to_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mod, "find_soffice", lambda: Path("/fake/soffice"))
    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *_a, **_k: SimpleNamespace(returncode=9, stderr="  ", stdout=""),
    )
    with pytest.raises(ParseFailedError, match="exit 9"):
        convert_doc_to_docx(tmp_path / "x.doc", tmp_path / "out")


def test_convert_writes_expected_stem_docx(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "report.doc"
    source.write_bytes(b"legacy")
    dest = tmp_path / "out"

    def fake_run(*_a, **_k):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "report.docx").write_bytes(b"PK-docx")
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    produced = convert_doc_to_docx(source, dest, soffice=Path("/fake/soffice"))
    assert produced == dest / "report.docx"


def test_convert_accepts_single_renamed_docx(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "report.doc"
    source.write_bytes(b"legacy")
    dest = tmp_path / "out"

    def fake_run(*_a, **_k):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "LibreOffice-renamed.docx").write_bytes(b"PK-docx")
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    produced = convert_doc_to_docx(source, dest, soffice=Path("/fake/soffice"))
    assert produced.name == "LibreOffice-renamed.docx"


def test_convert_fails_when_no_docx_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "report.doc"
    source.write_bytes(b"legacy")
    dest = tmp_path / "out"

    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *_a, **_k: SimpleNamespace(returncode=0, stderr="", stdout=""),
    )
    with pytest.raises(ParseFailedError, match="did not write a .docx"):
        convert_doc_to_docx(source, dest, soffice=Path("/fake/soffice"))


def test_convert_fails_when_multiple_docx_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "report.doc"
    source.write_bytes(b"legacy")
    dest = tmp_path / "out"

    def fake_run(*_a, **_k):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "a.docx").write_bytes(b"1")
        (dest / "b.docx").write_bytes(b"2")
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    with pytest.raises(ParseFailedError, match="did not write a .docx"):
        convert_doc_to_docx(source, dest, soffice=Path("/fake/soffice"))


def test_parse_doc_requires_soffice_when_none_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mod, "find_soffice", lambda: None)
    fake = tmp_path / "x.doc"
    fake.write_bytes(b"x")
    with pytest.raises(MissingLibreOfficeError):
        parse_doc(fake)


def test_parse_doc_converts_then_parses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sample = write_ordered_docx(tmp_path / "ordered.docx")
    fake_doc = tmp_path / "ordered.doc"
    fake_doc.write_bytes(b"legacy-bytes")

    def fake_convert(source: Path, dest_dir: Path, soffice: Path | None = None) -> Path:
        dest_dir.mkdir(parents=True, exist_ok=True)
        out = dest_dir / (source.stem + ".docx")
        out.write_bytes(sample.read_bytes())
        return out

    monkeypatch.setattr(mod, "find_soffice", lambda: Path("/fake/soffice"))
    monkeypatch.setattr(mod, "convert_doc_to_docx", fake_convert)
    blocks, converted = parse_doc(fake_doc)
    assert [b.text for b in blocks] == ["BEFORE_TABLE", "IN_TABLE", "AFTER_TABLE"]
    assert converted.suffix == ".docx"


def test_parse_doc_accepts_explicit_soffice_when_which_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sample = write_ordered_docx(tmp_path / "ordered.docx")
    fake_doc = tmp_path / "ordered.doc"
    fake_doc.write_bytes(b"legacy-bytes")

    def fake_convert(source: Path, dest_dir: Path, soffice: Path | None = None) -> Path:
        assert soffice == Path("/explicit/soffice")
        dest_dir.mkdir(parents=True, exist_ok=True)
        out = dest_dir / "ordered.docx"
        out.write_bytes(sample.read_bytes())
        return out

    monkeypatch.setattr(mod, "find_soffice", lambda: None)
    monkeypatch.setattr(mod, "convert_doc_to_docx", fake_convert)
    blocks, _converted = parse_doc(fake_doc, soffice=Path("/explicit/soffice"))
    assert "BEFORE_TABLE" in [b.text for b in blocks]
