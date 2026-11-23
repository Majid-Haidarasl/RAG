"""Phase 15 hardening: file hashing, ids and languages from names, repo root and bilingual pairs."""

import hashlib
from pathlib import Path

import pytest

from rag_core.ingestion.application.metadata import bilingual_pair_name, find_repo_root
from rag_core.ingestion.infrastructure.files import document_id_from_name, language_from_path, sha256_file
from rag_core.shared_kernel.language import LanguageCode

pytestmark = [pytest.mark.hardening, pytest.mark.ingestion]


def test_sha256_file(tmp_path: Path) -> None:
    full = tmp_path / "a.bin"
    full.write_bytes(b"phase 15")
    empty = tmp_path / "empty.bin"
    empty.write_bytes(b"")
    assert sha256_file(full) == hashlib.sha256(b"phase 15").hexdigest()
    assert sha256_file(empty) == hashlib.sha256(b"").hexdigest()


@pytest.mark.parametrize(("name", "doc_id"), [
    ("AR-FIN-008-report.docx", "AR-FIN-008"),
    ("ar-hr-۰۰۵-x.pdf", "AR-HR-005"),
    ("notes-2024.txt", "notes"),
])
def test_document_id_from_name(name: str, doc_id: str) -> None:
    assert document_id_from_name(Path(name)) == doc_id


@pytest.mark.parametrize(("path", "language"), [
    ("corpus/fa/x.docx", "fa"),
    ("corpus/EN/x.docx", "en"),
    ("x-fa.docx", "fa"),
    ("doc.pdf", None),
])
def test_language_from_path(path: str, language: str | None) -> None:
    assert language_from_path(Path(path)) == language


def test_find_repo_root_walks_upward(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (tmp_path / "schemas").mkdir()
    (tmp_path / "schemas" / "knowledge-metadata.json").write_text("{}", encoding="utf-8")
    deep = tmp_path / "a" / "b"
    deep.mkdir(parents=True)
    assert find_repo_root(deep) == tmp_path.resolve()


def test_find_repo_root_needs_schema(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        find_repo_root(tmp_path)


def _pair(tmp_path: Path) -> Path:
    for lang, name in (("fa", "AR-HR-005-a.docx"), ("en", "AR-HR-005-b.docx")):
        (tmp_path / lang).mkdir(exist_ok=True)
        (tmp_path / lang / name).write_bytes(b"x")
    return tmp_path / "fa" / "AR-HR-005-a.docx"


def test_bilingual_pair_found(tmp_path: Path) -> None:
    assert bilingual_pair_name(_pair(tmp_path), LanguageCode.FA) == "AR-HR-005-b.docx"


def test_bilingual_pair_without_language(tmp_path: Path) -> None:
    assert bilingual_pair_name(_pair(tmp_path), None) is None


def test_bilingual_pair_outside_language_folder(tmp_path: Path) -> None:
    other = tmp_path / "misc" / "AR-HR-005-a.docx"
    other.parent.mkdir()
    other.write_bytes(b"x")
    assert bilingual_pair_name(other, LanguageCode.FA) is None


def test_bilingual_pair_missing_other_folder(tmp_path: Path) -> None:
    (tmp_path / "en").mkdir()
    only = tmp_path / "en" / "AR-HR-005-b.docx"
    only.write_bytes(b"x")
    assert bilingual_pair_name(only, LanguageCode.EN) is None
