"""Render PDF pages to PNG for LVM OCR (optional Pillow + pypdfium2)."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path


class PdfRenderError(RuntimeError):
    """Page could not be rendered (missing libs or pdfplumber failure)."""


def render_pdf_page_png(path: Path, page_number: int, *, dpi: int = 150) -> bytes:
    """Return PNG bytes for a 1-based page. Raises ``PdfRenderError`` on failure."""
    try:
        import pdfplumber
    except ImportError as exc:
        raise PdfRenderError("pdfplumber is not installed") from exc
    try:
        from PIL import Image  # noqa: F401 — required by page.to_image
    except ImportError as exc:
        raise PdfRenderError(
            "Pillow is required for LVM page rendering; pip install 'rag-core[lvm]'"
        ) from exc

    path = Path(path)
    try:
        with pdfplumber.open(path) as pdf:
            if page_number < 1 or page_number > len(pdf.pages):
                raise PdfRenderError(
                    f"page {page_number} out of range (1..{len(pdf.pages)})"
                )
            page = pdf.pages[page_number - 1]
            try:
                page_image = page.to_image(resolution=dpi)
            except ImportError as exc:
                raise PdfRenderError(
                    "pypdfium2 is required for LVM page rendering; "
                    "pip install 'rag-core[lvm]'"
                ) from exc
            image = page_image.original
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            return buffer.getvalue()
    except PdfRenderError:
        raise
    except Exception as exc:
        raise PdfRenderError(f"cannot render page {page_number} of {path}: {exc}") from exc
