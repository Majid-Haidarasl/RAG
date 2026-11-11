"""Stable identifiers shared across contexts. Values are immutable."""

from __future__ import annotations

from dataclasses import dataclass
import re

from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.numerals import normalize_digits

_NODE_RE = re.compile(r"^N-[A-Z0-9]+(?:-[A-Z0-9]+)*$")
# Corpus documents: AR-ORG-001. Contracts/RFPs may add a year group: AR-CNT-1402-118, AR-RFP-1403-07.
_DOC_RE = re.compile(r"^AR-[A-Z]{2,5}-\d{2,4}(?:-\d{2,4})?$")
_ISSUE_RE = re.compile(r"^AR-ISS-\d{3}(?:/[A-Z0-9]+)?$")
_EXEC_RE = re.compile(r"^EX-[A-Z0-9]+(?:-[A-Z0-9]+)*$")
_PROJECT_RE = re.compile(r"^PRJ-[A-Z0-9]+(?:-[A-Z0-9]+)*$")
_RFP_RE = re.compile(r"^AR-RFP-\d{4}-\d{2}$")
_ITEM_RE = re.compile(r"^[A-Z0-9][A-Z0-9_.@/-]*$")


def _require(pattern: re.Pattern[str], value: str, label: str) -> str:
    if not pattern.match(value):
        raise InvariantError(f"invalid {label}: {value!r}")
    return value


@dataclass(frozen=True, order=True)
class NodeIdentifier:
    """Stable node id such as ``N-SW-WEB`` or ``N-BRD``."""

    value: str

    def __post_init__(self) -> None:
        text = self.value.strip()
        object.__setattr__(self, "value", _require(_NODE_RE, text, "NodeIdentifier"))

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, order=True)
class DocumentId:
    """Corpus or generated document identifier, always stored with Latin digits.

    ``AR-FIN-۰۰۸`` normalizes to ``AR-FIN-008`` (data-quality finding D1).
    """

    value: str

    def __post_init__(self) -> None:
        text = normalize_digits(self.value.strip()).upper()
        object.__setattr__(self, "value", _require(_DOC_RE, text, "DocumentId"))

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, order=True)
class IssueId:
    """Issue or sub-issue id: ``AR-ISS-024`` or ``AR-ISS-024/WIN``."""

    value: str

    def __post_init__(self) -> None:
        text = normalize_digits(self.value.strip()).upper()
        object.__setattr__(self, "value", _require(_ISSUE_RE, text, "IssueId"))

    def __str__(self) -> str:
        return self.value

    @property
    def parent_id(self) -> IssueId | None:
        if "/" not in self.value:
            return None
        return IssueId(self.value.split("/", 1)[0])

    @property
    def is_subissue(self) -> bool:
        return "/" in self.value

    @property
    def suffix(self) -> str | None:
        if "/" not in self.value:
            return None
        return self.value.split("/", 1)[1]


@dataclass(frozen=True, order=True)
class ExecutorId:
    """Synthetic executor key, e.g. ``EX-ROOZBEH-MOHSENI``."""

    value: str

    def __post_init__(self) -> None:
        text = self.value.strip().upper().replace(" ", "-")
        object.__setattr__(self, "value", _require(_EXEC_RE, text, "ExecutorId"))

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, order=True)
class ProjectId:
    value: str

    def __post_init__(self) -> None:
        text = normalize_digits(self.value.strip()).upper()
        object.__setattr__(self, "value", _require(_PROJECT_RE, text, "ProjectId"))

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, order=True)
class RfpId:
    value: str

    def __post_init__(self) -> None:
        text = normalize_digits(self.value.strip()).upper()
        object.__setattr__(self, "value", _require(_RFP_RE, text, "RfpId"))

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, order=True)
class KnowledgeItemId:
    """Stable knowledge identity; usually the same string as the DocumentId."""

    value: str

    def __post_init__(self) -> None:
        text = normalize_digits(self.value.strip())
        # Prefer document-shaped ids when they match.
        object.__setattr__(self, "value", text)
        if not _ITEM_RE.match(self.value) and not _DOC_RE.match(self.value.upper()):
            raise InvariantError(f"invalid KnowledgeItemId: {self.value!r}")
        if _DOC_RE.match(self.value.upper()):
            object.__setattr__(self, "value", self.value.upper())

    def __str__(self) -> str:
        return self.value

    def as_document_id(self) -> DocumentId:
        return DocumentId(self.value)
