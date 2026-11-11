"""Ingestion → lifecycle mapping with real (tiny) DOCX files."""

import shutil
from pathlib import Path

import pytest
from docx import Document

from rag_core.ingestion.application.pipeline import ingest_file
from rag_core.knowledge.application.lifecycle import KnowledgeLifecycleService
from rag_core.knowledge.domain.model import ChunkStatus, VersionStatus, VersionTag
from rag_core.shared_kernel.language import LanguageCode
from tests.fixtures.ingestion.builders import write_sample_docx

pytestmark = [pytest.mark.knowledge, pytest.mark.lifecycle]

REPO = Path(__file__).resolve().parents[3]


def _copy_to(tmp: Path, lang: str, name: str, src: Path) -> Path:
    target = tmp / "corpus" / lang / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, target)
    return target


def _fa_doc(tmp: Path) -> Path:
    src = write_sample_docx(tmp / "src.docx")
    return _copy_to(tmp, "fa", "AR-HW-012-تعمیرات.docx", src)


def test_first_ingest_registers_then_unchanged_is_noop(tmp_path: Path) -> None:
    path = _fa_doc(tmp_path)
    svc = KnowledgeLifecycleService()
    first = svc.ingest(ingest_file(path, repo_root=REPO))
    again = svc.ingest(ingest_file(path, repo_root=REPO))
    assert (first.action, first.version) == ("registered", "1.0")
    assert (again.action, again.version) == ("unchanged", "1.0")


def test_changed_file_creates_new_version_and_retires_old_chunks(tmp_path: Path) -> None:
    path = _fa_doc(tmp_path)
    svc = KnowledgeLifecycleService()
    svc.ingest(ingest_file(path, repo_root=REPO))
    doc = Document(str(path))
    doc.add_paragraph("بند افزوده: مهلت تحویل دستگاه به ۵ روز کاری کاهش یافت.")
    doc.save(str(path))
    outcome = svc.ingest(ingest_file(path, repo_root=REPO))
    assert (outcome.action, outcome.version) == ("new_version", "1.1")
    item = svc.items()[0]
    old = item.get_version(VersionTag(1, 0), LanguageCode.FA)
    assert old.status is VersionStatus.SUPERSEDED
    assert old.count(ChunkStatus.RETIRED) == len(old.chunks)
    assert item.active_version(LanguageCode.FA).supersedes == VersionTag(1, 0)


def test_english_file_joins_same_item_as_language_version(tmp_path: Path) -> None:
    src = write_sample_docx(tmp_path / "src.docx")
    fa = _copy_to(tmp_path, "fa", "AR-HW-012-تعمیرات.docx", src)
    en = _copy_to(tmp_path, "en", "AR-HW-012-repair.docx", src)
    svc = KnowledgeLifecycleService()
    svc.ingest(ingest_file(fa, repo_root=REPO))
    outcome = svc.ingest(ingest_file(en, repo_root=REPO))
    assert outcome.action == "added_language"
    assert len(svc.items()) == 1
