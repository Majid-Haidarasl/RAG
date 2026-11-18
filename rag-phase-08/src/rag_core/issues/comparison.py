"""Public entry point required by issue #7 (``src/issues/comparison.py``).

The implementation lives in the domain layer: ``rag_core.issues.domain.comparison``.
"""

from rag_core.issues.domain.comparison import *  # noqa: F401,F403
from rag_core.issues.domain.comparison import (  # noqa: F401
    DUPLICATE_MIN_TEXT,
    DUPLICATE_SCORE,
    RELATED_SCORE,
    Candidate,
    ComparisonConfig,
    ComparisonResult,
    IssueComparator,
    IssueProfile,
    MatchLabel,
    content_tokens,
)
