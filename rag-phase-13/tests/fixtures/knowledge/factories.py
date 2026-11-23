"""Builders for Phase 5 knowledge lifecycle and dedup tests."""

from __future__ import annotations

from datetime import date

from rag_core.knowledge.domain.dedup import TextRecord
from rag_core.knowledge.domain.model import KnowledgeChunk, KnowledgeItem, VersionTag
from rag_core.shared_kernel.confidentiality import Confidentiality
from rag_core.shared_kernel.identifiers import DocumentId, NodeIdentifier
from rag_core.shared_kernel.language import LanguageCode

FA = LanguageCode.FA
EN = LanguageCode.EN
D0 = date(2024, 10, 1)
D1 = date(2025, 3, 1)
D2 = date(2025, 9, 1)


def chunks(prefix: str, *texts: str) -> list[KnowledgeChunk]:
    return [
        KnowledgeChunk(chunk_id=f"{prefix}#c{i:04d}", order=i, text=t, heading_path="s")
        for i, t in enumerate(texts, start=1)
    ]


def item(
    doc: str = "AR-HW-012",
    language: LanguageCode = FA,
    texts: tuple[str, ...] = ("بند یک تعمیرات", "بند دو تعمیرات"),
    sha: str = "sha-v1",
    on: date = D0,
) -> KnowledgeItem:
    return KnowledgeItem.register(
        document_id=DocumentId(doc),
        owning_node=NodeIdentifier("N-HW-REP"),
        confidentiality=Confidentiality.INTERNAL,
        subject_domain="hardware procedure",
        language=language,
        version=VersionTag(1, 0),
        chunks=chunks(doc, *texts),
        file_sha256=sha,
        effective_from=on,
    )


def record(key: str, text: str, doc: str = "AR-X-001", lang: str | None = "en", source: str | None = None) -> TextRecord:
    return TextRecord(key=key, document_id=doc, language=lang, source=source or key, text=text)


LOREM_EN = (
    "The repair desk records every incoming laptop with its asset tag, the reported fault, "
    "the customer contact and the promised return date before any diagnosis starts. "
    "A technician confirms the fault, estimates parts and labour, and asks for written approval "
    "when the estimate exceeds the warranty limit or the agreed service budget for the month."
)
LOREM_FA = (
    "میز تعمیرات هر لپ‌تاپ ورودی را با برچسب دارایی، خرابی گزارش‌شده، اطلاعات تماس مشتری و "
    "تاریخ تحویل وعده‌داده‌شده پیش از شروع عیب‌یابی ثبت می‌کند. تکنسین خرابی را تأیید، قطعات و "
    "دستمزد را برآورد و هنگامی که برآورد از سقف ضمانت یا بودجه توافق‌شده بیشتر شود تأیید کتبی می‌گیرد."
)
