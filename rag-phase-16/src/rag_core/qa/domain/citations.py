"""Parse ``[AR-HR-005 §12]`` citations and verify them against the context.

Accepted forms inside square brackets (Persian digits are normalized):
``[AR-HR-005 §12]``, ``[AR-HR-005 § 12/en]``, ``[AR-HR-005#c0012]``,
several refs separated by ``;`` ``,`` ``،`` ``؛``, and a document-level
``[AR-HR-005]``. A citation is *valid* only if it points at a block that
was actually given to the model; a document-level citation is valid if a
block of that document was given (granularity "document").
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from rag_core.rag.domain.context import AssembledContext, ContextBlock
from rag_core.shared_kernel.numerals import normalize_digits

_BRACKET_RE = re.compile(r"\[([^\[\]]{3,200})\]")
_REF_RE = re.compile(
    r"(?P<doc>AR-[A-Z]{2,5}-\d{2,4}(?:-\d{2,4})?)"
    r"(?:\s*(?:§\s*(?P<sec>\d+)|#c(?P<cid>\d+))(?:\s*/\s*(?P<lang>fa|en))?)?",
    re.IGNORECASE,
)
_SPLIT_RE = re.compile(r"[;,،؛]")


@dataclass(frozen=True)
class ParsedCitation:
    raw: str
    document_id: str
    order: int | None = None
    language: str | None = None

    @property
    def label(self) -> str:
        base = self.document_id if self.order is None else f"{self.document_id} §{self.order}"
        return f"{base}/{self.language}" if self.language else base


@dataclass(frozen=True)
class VerifiedCitation:
    citation: ParsedCitation
    valid: bool
    granularity: str  # "chunk" | "document" | "none"
    block_labels: tuple[str, ...] = ()
    reason: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "label": self.citation.label, "raw": self.citation.raw, "valid": self.valid,
            "granularity": self.granularity, "blocks": list(self.block_labels), "reason": self.reason,
        }


def parse_citations(text: str) -> list[ParsedCitation]:
    found: list[ParsedCitation] = []
    seen: set[str] = set()
    for bracket in _BRACKET_RE.finditer(text or ""):
        inner = normalize_digits(bracket.group(1))
        for part in _SPLIT_RE.split(inner):
            m = _REF_RE.search(part.strip())
            if not m:
                continue
            sec = m.group("sec") or m.group("cid")
            cit = ParsedCitation(
                raw=part.strip(),
                document_id=m.group("doc").upper(),
                order=int(sec) if sec is not None else None,
                language=(m.group("lang") or "").lower() or None,
            )
            if cit.label not in seen:
                seen.add(cit.label)
                found.append(cit)
    return found


def strip_citations(text: str) -> str:
    """Answer text without bracketed references (used by the fact check)."""
    return _BRACKET_RE.sub(" ", text or "")


def _matches(block: ContextBlock, cit: ParsedCitation) -> bool:
    rec = block.hit.record
    if rec.document_id != cit.document_id:
        return False
    if cit.order is not None and rec.order != cit.order:
        return False
    if cit.language is not None and rec.language != cit.language:
        return False
    return True


def verify_citations(citations: list[ParsedCitation], context: AssembledContext) -> list[VerifiedCitation]:
    out: list[VerifiedCitation] = []
    for cit in citations:
        blocks = [b for b in context.blocks if _matches(b, cit)]
        if blocks:
            out.append(VerifiedCitation(cit, True, "chunk" if cit.order is not None else "document",
                                        tuple(b.label for b in blocks)))
            continue
        same_doc = any(b.hit.record.document_id == cit.document_id for b in context.blocks)
        reason = "section not in retrieved context" if same_doc else "document not in retrieved context"
        out.append(VerifiedCitation(cit, False, "none", (), reason))
    return out


def cited_blocks(verified: list[VerifiedCitation], context: AssembledContext) -> list[ContextBlock]:
    labels = {lab for v in verified if v.valid for lab in v.block_labels}
    return [b for b in context.blocks if b.label in labels]
