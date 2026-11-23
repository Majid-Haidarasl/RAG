"""Expertise metadata: a small, explainable term vocabulary per executor.

The registry language is English, so terms are English content words:
lower-cased, split on anything that is not a letter or digit, stopwords and
pure numbers dropped, and a light plural / ``-ing`` strip applied on both
sides (``dashboards`` = ``dashboard``, ``reporting`` = ``report``,
``penalties`` = ``penalty``). Persian letters are kept as tokens, so a
Persian text simply finds no English term instead of failing.

An executor's vocabulary comes from three registry fields: specialty,
allowed referral domains and expertise tags. Outputs and authority limits
are not expertise and are left out on purpose.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from rag_core.executors.domain.model import Executor

STOPWORDS = frozenset(
    """
    a an the and or of in on at to for from by with within without as is are be been
    not no non versus vs per via into onto its it this that these those their his her
    after before than then other any all each such only also
    """.split()
)

_TOKEN_RE = re.compile(r"[a-z0-9\u0600-\u06ff]+")


def stem(token: str) -> str:
    """Light, deterministic suffix strip (same rule for profile and request)."""
    if len(token) > 5 and token.endswith("ing"):
        return token[:-3]
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def terms(text: str) -> frozenset[str]:
    out: set[str] = set()
    for raw in _TOKEN_RE.findall((text or "").lower()):
        if len(raw) < 2 or raw.isdigit() or raw in STOPWORDS:
            continue
        out.add(stem(raw))
    return frozenset(out)


def terms_of(texts: Iterable[str]) -> frozenset[str]:
    out: set[str] = set()
    for t in texts:
        out |= terms(t)
    return frozenset(out)


@dataclass(frozen=True)
class ExpertiseProfile:
    """Vocabulary of one executor, kept per source field for explanations."""

    executor_id: str
    specialty: frozenset[str]
    domains: frozenset[str]
    tags: frozenset[str]

    @classmethod
    def of(cls, executor: Executor) -> ExpertiseProfile:
        return cls(
            str(executor.identifier),
            terms_of(executor.specialty),
            terms_of(executor.allowed_referral_domains),
            terms_of(str(t) for t in executor.expertise),
        )

    @property
    def vocabulary(self) -> frozenset[str]:
        return self.specialty | self.domains | self.tags

    def matched(self, request_terms: frozenset[str]) -> tuple[str, ...]:
        """Profile terms that occur in the request, sorted for stable output."""
        return tuple(sorted(self.vocabulary & request_terms))

    def matched_domain_terms(self, request_terms: frozenset[str]) -> tuple[str, ...]:
        return tuple(sorted(self.domains & request_terms))
