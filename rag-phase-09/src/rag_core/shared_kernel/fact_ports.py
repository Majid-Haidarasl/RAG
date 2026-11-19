"""Port for post-generation verification of names, IDs and numbers.

The design is in ``docs/phase-03/fact-validator-design.md``. A complete
implementation ships in Phase 8. This Protocol is the contract other
contexts depend on, so they do not grow an implicit coupling to one
algorithm.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from rag_core.shared_kernel.identifiers import DocumentId


class FactKind(StrEnum):
    PERSON_NAME = "person_name"
    DOCUMENT_ID = "document_id"
    NODE_ID = "node_id"
    ISSUE_ID = "issue_id"
    NUMBER = "number"
    MONEY = "money"
    DATE = "date"


class FactVerdict(StrEnum):
    CONFIRMED = "confirmed"
    CORRECTED = "corrected"
    FLAGGED = "flagged"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class FactClaim:
    kind: FactKind
    raw_text: str
    normalized: str


@dataclass(frozen=True)
class FactCheckResult:
    claim: FactClaim
    verdict: FactVerdict
    evidence_document_id: DocumentId | None = None
    evidence_span: str | None = None
    replacement: str | None = None
    notes: str = ""


@dataclass(frozen=True)
class FactValidationReport:
    results: tuple[FactCheckResult, ...] = field(default_factory=tuple)

    @property
    def all_supported(self) -> bool:
        return all(
            r.verdict in {FactVerdict.CONFIRMED, FactVerdict.CORRECTED}
            for r in self.results
        )

    @property
    def unsupported(self) -> tuple[FactCheckResult, ...]:
        return tuple(r for r in self.results if r.verdict == FactVerdict.UNSUPPORTED)


class FactValidator(Protocol):
    """Verify extracted claims against source chunks and registries."""

    def validate(
        self,
        generated_text: str,
        source_texts: list[str],
        *,
        source_document_ids: list[DocumentId] | None = None,
    ) -> FactValidationReport:
        ...
