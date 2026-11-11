"""Shared kernel used by every bounded context.

Only types that truly share one meaning across contexts live here:
identifiers, layer index, language, confidentiality, errors, events,
and numeral/identifier normalization (the foundation of fact validation).
"""

from rag_core.shared_kernel.errors import DomainError, InvariantError
from rag_core.shared_kernel.events import DomainEvent
from rag_core.shared_kernel.identifiers import (
    DocumentId,
    ExecutorId,
    IssueId,
    KnowledgeItemId,
    NodeIdentifier,
    ProjectId,
    RfpId,
)
from rag_core.shared_kernel.language import LanguageCode
from rag_core.shared_kernel.layer import LayerIndex
from rag_core.shared_kernel.confidentiality import Confidentiality
from rag_core.shared_kernel.numerals import (
    normalize_digits,
    parse_decimal,
    strip_thousands_separators,
)

__all__ = [
    "Confidentiality",
    "DocumentId",
    "DomainError",
    "DomainEvent",
    "ExecutorId",
    "InvariantError",
    "IssueId",
    "KnowledgeItemId",
    "LanguageCode",
    "LayerIndex",
    "NodeIdentifier",
    "ProjectId",
    "RfpId",
    "normalize_digits",
    "parse_decimal",
    "strip_thousands_separators",
]
