"""LVM-assisted PDF page extraction (unit doubles only; no live Ollama)."""

from pathlib import Path

import pytest

from rag_core.ingestion.application.pipeline import ingest_file
from rag_core.ingestion.infrastructure.lvm_prompt import load_lvm_prompt
from rag_core.models.infrastructure.memory import InMemoryModelRegistry
from rag_core.rag.infrastructure.ollama import (
    OllamaClient,
    OllamaError,
    OllamaLvmAdapter,
)
from tests.fakes.models import FakeLvm
from tests.fixtures.ingestion.builders import write_scanned_pdf
from tests.fixtures.rag.fakes import FakeOllamaServer

pytestmark = pytest.mark.ingestion

REPO = Path(__file__).resolve().parents[3]


def test_scanned_page_with_lvm_yields_tagged_chunk(tmp_path: Path, monkeypatch) -> None:
    path = write_scanned_pdf(tmp_path / "en" / "AR-SW-022-scan.pdf")
    fake = FakeLvm("Scanned page text from LVM.")

    def fake_render(_path: Path, page_number: int, *, dpi: int = 150) -> bytes:
        assert page_number == 1 and dpi == 150
        return b"fake-png-bytes"

    monkeypatch.setattr(
        "rag_core.ingestion.application.pipeline.render_pdf_page_png", fake_render
    )
    doc = ingest_file(
        path,
        repo_root=REPO,
        lvm=fake,
        lvm_enabled=True,
        lvm_prompt="Extract text",
        lvm_dpi=150,
    )
    lvm_chunks = [c for c in doc.chunks if c.extraction == "lvm"]
    assert len(lvm_chunks) == 1
    chunk = lvm_chunks[0]
    assert chunk.text == "Scanned page text from LVM."
    assert chunk.anchors[0].page == 1
    assert chunk.anchors[0].document_id == "AR-SW-022"
    assert chunk.version == "1.0"
    assert not any("LVM OCR is deferred" in w for w in doc.warnings)
    assert len(fake.calls) == 1


def test_lvm_disabled_keeps_deferred_warning(tmp_path: Path) -> None:
    path = write_scanned_pdf(tmp_path / "en" / "AR-SW-022-scan.pdf")
    doc = ingest_file(path, repo_root=REPO, lvm=FakeLvm(), lvm_enabled=False)
    assert doc.is_scanned is True
    assert any("LVM OCR is deferred" in w for w in doc.warnings)
    assert not any(c.extraction == "lvm" for c in doc.chunks)


def test_render_failure_falls_back_to_deferred_warning(
    tmp_path: Path, monkeypatch
) -> None:
    from rag_core.ingestion.infrastructure.pdf_render import PdfRenderError

    path = write_scanned_pdf(tmp_path / "en" / "AR-SW-022-scan.pdf")

    def boom(*_a, **_k):
        raise PdfRenderError("Pillow is required")

    monkeypatch.setattr(
        "rag_core.ingestion.application.pipeline.render_pdf_page_png", boom
    )
    doc = ingest_file(
        path, repo_root=REPO, lvm=FakeLvm(), lvm_enabled=True, lvm_prompt="x"
    )
    assert any("LVM OCR is deferred" in w for w in doc.warnings)
    assert not any(c.extraction == "lvm" for c in doc.chunks)


def test_non_local_ollama_url_rejected_for_lvm() -> None:
    with pytest.raises(OllamaError, match="local"):
        OllamaLvmAdapter(OllamaClient("http://example.com:11434"))


def test_ollama_lvm_adapter_sends_image_and_keep_alive_zero() -> None:
    registry = InMemoryModelRegistry()
    model = registry.get("lvm-qwen2.5vl-3b").ollama_name
    with FakeOllamaServer(models=(model,), chat_reply=lambda m: "page text") as srv:
        adapter = OllamaLvmAdapter(
            OllamaClient(srv.url, timeout_s=5), model=model, keep_alive="0"
        )
        result = adapter.read(b"\x89PNG", "Extract text")
        bodies = [b for p, b in srv.requests if p == "/api/chat"]
    assert result.text == "page text"
    assert bodies[0]["keep_alive"] == "0"
    assert bodies[0]["model"] == model
    assert "images" in bodies[0]["messages"][0]


def test_lvm_page_prompt_loads() -> None:
    prompt = load_lvm_prompt(REPO / "config" / "prompts" / "lvm")
    assert prompt.prompt_id == "lvm.page_text"
    assert "Extract" in prompt.task_prompt
