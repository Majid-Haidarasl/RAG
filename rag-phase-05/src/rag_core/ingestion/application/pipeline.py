"""Parse → normalize → metadata → chunk. Local files only."""

from __future__ import annotations

from pathlib import Path

from rag_core.ingestion.application.chunking import chunk_blocks
from rag_core.ingestion.application.metadata import build_metadata
from rag_core.ingestion.domain.model import (
    ContentBlock,
    FileFormat,
    IngestedDocument,
    NormalizationReport,
)
from rag_core.ingestion.infrastructure.dispatcher import CompositeDocumentParser, ParsedWithBlocks
from rag_core.ingestion.infrastructure.files import document_id_from_name, language_from_path, sha256_file
from rag_core.shared_kernel.language import LanguageCode
from rag_core.shared_kernel.persian import merge_counts, normalize_document_ids, normalize_persian_text


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


def ingest_file(
    path: Path,
    *,
    parser: CompositeDocumentParser | None = None,
    repo_root: Path | None = None,
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
            repo_root=repo_root,
        )
    except FileNotFoundError as exc:
        metadata = {
            "id": document_id,
            "language": None if language is None else language.value,
            "file_sha256": file_hash,
            "metadata_error": f"schema not found: {exc}",
        }
    warnings: list[str] = []
    if parsed.is_scanned:
        warnings.append(
            "scanned or image-only PDF pages detected; LVM OCR is deferred "
            f"(pages {', '.join(str(p) for p in parsed.scanned_pages) or 'unknown'})"
        )
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
