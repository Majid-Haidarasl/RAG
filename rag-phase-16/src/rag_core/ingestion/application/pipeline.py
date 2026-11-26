"""Parse → normalize → metadata → chunk. Local files only."""

from __future__ import annotations

from pathlib import Path

from rag_core.ingestion.application.chunking import chunk_blocks
from rag_core.ingestion.application.metadata import build_metadata
from rag_core.ingestion.domain.model import (
    ContentBlock,
    IngestedDocument,
    NormalizationReport,
    SourceAnchor,
    TextChunk,
)
from rag_core.ingestion.infrastructure.dispatcher import (
    CompositeDocumentParser,
    ParsedWithBlocks,
)
from rag_core.ingestion.infrastructure.files import (
    document_id_from_name,
    language_from_path,
    sha256_file,
)
from rag_core.ingestion.infrastructure.pdf_render import (
    PdfRenderError,
    render_pdf_page_png,
)
from rag_core.models.domain.ports import LvmPort
from rag_core.shared_kernel.language import LanguageCode
from rag_core.shared_kernel.persian import (
    merge_counts,
    normalize_document_ids,
    normalize_persian_text,
)

_DEFERRED_LVM = "scanned or image-only PDF pages detected; LVM OCR is deferred"


def _normalize_blocks(
    blocks: tuple[ContentBlock, ...] | list[ContentBlock],
    language: LanguageCode | None,
) -> tuple[list[ContentBlock], NormalizationReport]:
    lang = None if language is None else language.value
    totals = {"yeh_kaf": 0, "zwnj": 0, "id_digits": 0, "arabic_indic": 0}
    replacements: list[tuple[str, str]] = []
    out: list[ContentBlock] = []
    for block in blocks:
        text, counts = normalize_persian_text(block.text, language=lang)
        _, id_fixes = normalize_document_ids(block.text)
        replacements.extend(id_fixes)
        totals = merge_counts(totals, counts)
        cells = block.cells
        if cells:
            new_rows = []
            for row in cells:
                new_row = []
                for cell in row:
                    cell_text, cell_counts = normalize_persian_text(cell, language=lang)
                    totals = merge_counts(totals, cell_counts)
                    new_row.append(cell_text)
                new_rows.append(tuple(new_row))
            cells = tuple(new_rows)
        path = block.heading_path
        if path:
            path, path_counts = normalize_persian_text(path, language=lang)
            totals = merge_counts(totals, path_counts)
        out.append(
            ContentBlock(
                kind=block.kind,
                text=text,
                index=block.index,
                heading_path=path,
                heading_level=block.heading_level,
                page=block.page,
                paragraph_index=block.paragraph_index,
                table_index=block.table_index,
                row=block.row,
                column=block.column,
                cells=cells,
            )
        )
    report = NormalizationReport(
        yeh_kaf=totals["yeh_kaf"],
        zwnj=totals["zwnj"],
        id_digits=totals["id_digits"],
        arabic_indic=totals["arabic_indic"],
        replacements=replacements,
    )
    return out, report


def _deferred_warning(pages: tuple[int, ...] | list[int]) -> str:
    listed = ", ".join(str(p) for p in pages) or "unknown"
    return f"{_DEFERRED_LVM} (pages {listed})"


def _lvm_page_numbers(
    *,
    is_scanned: bool,
    scanned_pages: tuple[int, ...],
    visual_layout: bool,
    page_count: int,
) -> list[int]:
    pages: set[int] = set()
    if is_scanned:
        pages.update(scanned_pages or range(1, page_count + 1))
    if visual_layout and page_count > 0:
        pages.update(range(1, page_count + 1))
    return sorted(pages)


def _extract_lvm_chunks(
    path: Path,
    *,
    document_id: str,
    version: str,
    pages: list[int],
    language: LanguageCode | None,
    lvm: LvmPort,
    prompt: str,
    dpi: int,
    start_order: int,
) -> tuple[list[TextChunk], list[int], NormalizationReport]:
    """Run LVM on pages; return chunks, pages that failed, and normalization totals."""
    lang = None if language is None else language.value
    totals = {"yeh_kaf": 0, "zwnj": 0, "id_digits": 0, "arabic_indic": 0}
    replacements: list[tuple[str, str]] = []
    chunks: list[TextChunk] = []
    failed: list[int] = []
    order = start_order
    for page in pages:
        try:
            png = render_pdf_page_png(path, page, dpi=dpi)
            result = lvm.read(png, prompt)
        except (PdfRenderError, OSError, RuntimeError):
            failed.append(page)
            continue
        text, counts = normalize_persian_text(result.text or "", language=lang)
        _, id_fixes = normalize_document_ids(text)
        replacements.extend(id_fixes)
        totals = merge_counts(totals, counts)
        text = text.strip()
        if not text:
            failed.append(page)
            continue
        order += 1
        chunks.append(
            TextChunk(
                chunk_id=f"{document_id}#c{order:04d}",
                order=order,
                text=text,
                heading_path="",
                anchors=(
                    SourceAnchor(
                        document_id=document_id,
                        block_index=page,
                        char_start=0,
                        char_end=len(text),
                        page=page,
                    ),
                ),
                kind="lvm_page",
                extraction="lvm",
                version=version,
            )
        )
    report = NormalizationReport(
        yeh_kaf=totals["yeh_kaf"],
        zwnj=totals["zwnj"],
        id_digits=totals["id_digits"],
        arabic_indic=totals["arabic_indic"],
        replacements=replacements,
    )
    return chunks, failed, report


def ingest_file(
    path: Path,
    *,
    parser: CompositeDocumentParser | None = None,
    repo_root: Path | None = None,
    lvm: LvmPort | None = None,
    lvm_enabled: bool = False,
    lvm_prompt: str = "",
    lvm_dpi: int = 150,
    visual_layout: bool = False,
) -> IngestedDocument:
    path = Path(path)
    parser = parser or CompositeDocumentParser()
    parsed: ParsedWithBlocks = parser.parse(path)  # type: ignore[assignment]
    lang_hint = language_from_path(path)
    language = LanguageCode.parse(lang_hint) if lang_hint else parsed.language
    document_id = document_id_from_name(path)
    blocks, report = _normalize_blocks(parsed.blocks, language)
    text = "\n\n".join(b.text for b in blocks if b.text.strip())
    headings = tuple(b.text for b in blocks if b.kind.value == "heading")
    chunks = chunk_blocks(blocks, document_id=document_id)
    file_hash = sha256_file(path)
    byte_size = path.stat().st_size
    file_format = parsed.file_format
    try:
        metadata = build_metadata(
            document_id=document_id,
            path=path,
            language=language,
            file_sha256=file_hash,
            byte_size=byte_size,
            file_format=file_format.value,
            page_count=parsed.page_count,
            is_scanned=parsed.is_scanned,
            chunk_count=len(chunks),
            char_count=len(text),
            visual_layout=visual_layout,
            repo_root=repo_root,
        )
    except FileNotFoundError as exc:
        metadata = {
            "id": document_id,
            "language": None if language is None else language.value,
            "file_sha256": file_hash,
            "metadata_error": f"schema not found: {exc}",
            "visual_layout": visual_layout,
            "version": "1.0",
        }
    warnings: list[str] = list(getattr(parsed, "warnings", ()) or ())
    needs_lvm = parsed.is_scanned or bool(metadata.get("visual_layout"))
    lvm_pages = _lvm_page_numbers(
        is_scanned=parsed.is_scanned,
        scanned_pages=parsed.scanned_pages,
        visual_layout=bool(metadata.get("visual_layout")),
        page_count=parsed.page_count,
    )
    if needs_lvm and lvm_enabled and lvm is not None and lvm_pages:
        version = str(metadata.get("version") or "1.0")
        prompt = lvm_prompt.strip() or "Extract all readable text from this page image."
        lvm_chunks, failed_pages, lvm_report = _extract_lvm_chunks(
            path,
            document_id=document_id,
            version=version,
            pages=lvm_pages,
            language=language,
            lvm=lvm,
            prompt=prompt,
            dpi=lvm_dpi,
            start_order=len(chunks),
        )
        report = NormalizationReport(
            yeh_kaf=report.yeh_kaf + lvm_report.yeh_kaf,
            zwnj=report.zwnj + lvm_report.zwnj,
            id_digits=report.id_digits + lvm_report.id_digits,
            arabic_indic=report.arabic_indic + lvm_report.arabic_indic,
            replacements=[*report.replacements, *lvm_report.replacements],
        )
        chunks = [*chunks, *lvm_chunks]
        if lvm_chunks:
            text = "\n\n".join(
                part for part in [text, *[c.text for c in lvm_chunks]] if part.strip()
            )
            metadata["chunk_count"] = len(chunks)
            metadata["char_count"] = len(text)
        if failed_pages:
            warnings.append(_deferred_warning(tuple(failed_pages)))
    elif needs_lvm:
        warnings.append(_deferred_warning(parsed.scanned_pages or tuple(lvm_pages)))
    return IngestedDocument(
        path=path,
        file_format=file_format,
        document_id=document_id,
        language=language,
        text=text,
        blocks=tuple(blocks),
        headings=headings,
        page_count=parsed.page_count,
        file_sha256=file_hash,
        byte_size=byte_size,
        is_scanned=parsed.is_scanned,
        scanned_pages=parsed.scanned_pages,
        normalization=report,
        metadata=metadata,
        chunks=tuple(chunks),
        warnings=warnings,
        converted_from=parsed.converted_from,
        extraction_engine=getattr(parsed, "extraction_engine", ""),
        text_quality=getattr(parsed, "text_quality", None),
    )


def ingest_paths(
    paths: list[Path],
    *,
    repo_root: Path | None = None,
) -> list[IngestedDocument | BaseException]:
    """Ingest many files; capture per-file exceptions instead of aborting the batch."""
    parser = CompositeDocumentParser()
    results: list[IngestedDocument | BaseException] = []
    for path in paths:
        try:
            results.append(ingest_file(path, parser=parser, repo_root=repo_root))
        except Exception as exc:  # noqa: BLE001 — batch must report each failure
            exc.path = path  # type: ignore[attr-defined]
            results.append(exc)
    return results
