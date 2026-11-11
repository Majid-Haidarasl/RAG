"""Ingestion-specific errors. These extend DomainError so application code can map them."""

from __future__ import annotations

from rag_core.shared_kernel.errors import DomainError

LIBREOFFICE_INSTALL = "sudo apt install -y libreoffice-writer --no-install-recommends"
POPPLER_INSTALL = "sudo apt install -y poppler-utils"


class IngestionError(DomainError):
    """A local file could not be parsed or converted."""


class UnsupportedFormatError(IngestionError):
    def __init__(self, suffix: str) -> None:
        super().__init__(
            f"unsupported document format {suffix!r}; expected .docx, .doc or .pdf"
        )
        self.suffix = suffix


class MissingLibreOfficeError(IngestionError):
    def __init__(self, path: str | None = None) -> None:
        where = f" for {path}" if path else ""
        super().__init__(
            "LibreOffice (soffice) is not installed; cannot convert a legacy .doc file"
            f"{where}. Install it with: {LIBREOFFICE_INSTALL}"
        )


class ParseFailedError(IngestionError):
    def __init__(self, path: str, reason: str) -> None:
        super().__init__(f"failed to parse {path}: {reason}")
        self.path = path
        self.reason = reason


class GarbledTextError(ParseFailedError):
    """Text was extracted but is not usable (cid glyphs, reversed order, ...)."""

    def __init__(self, path: str, reasons: tuple[str, ...], engine: str, hint: str = "") -> None:
        reason = f"garbled text from {engine}: " + "; ".join(reasons)
        if hint:
            reason += f". {hint}"
        super().__init__(path, reason)
        self.reasons = reasons
        self.engine = engine
