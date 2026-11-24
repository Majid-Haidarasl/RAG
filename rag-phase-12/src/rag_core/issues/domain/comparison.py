"""Deterministic, offline comparison of a new issue with existing issues.

Score per candidate (issue or sub-issue):

* ``text``  = max over the candidate's language texts (EN, FA) of
  0.5 · Jaccard(T_new, T_old) + 0.5 · containment(T_new ⊆ T_old)
  over Persian-normalized content tokens (Phase 5 ``fingerprint.tokens``:
  NFKC, Arabic ي/ك → Persian, digits → Latin, ZWNJ joined, punctuation
  removed; then stop-words and plural suffixes are dropped). Containment
  rewards a short new report that sits inside a longer bilingual record.
* ``meta``  = weighted overlap of nodes (0.35), documents (0.30), category
  (equal, 0.15) and contract (equal, 0.20). Node and document sets use the
  overlap coefficient |A∩B| / min(|A|,|B|): a new report usually names a
  subset of the nodes and documents of a broad existing issue. A field that is
  empty on both sides is skipped and the remaining weights are renormalized.
* ``score`` = 0.6 · text + 0.4 · meta. With an optional ``TextEmbedder``:
  0.45 · text + 0.20 · cosine + 0.35 · meta.

Labels (documented thresholds, see docs/phase-07/issue-model.md):

* duplicate: score ≥ 0.60 **and** text ≥ 0.45 (metadata alone never makes a duplicate)
* related:   score ≥ 0.25
* new:       otherwise

Records closed as duplicates are folded into their canonical issue: the
canonical candidate keeps the better of the two scores and notes ``via``.

MinHash signatures (Phase 5 ``MinHasher``) are used as a cheap prefilter
when the registry is large (``prefilter_min_candidates``); exact Jaccard
always decides the score, so results are identical with or without it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum

from rag_core.issues.domain.model import Issue, SubIssue
from rag_core.issues.domain.ports import TextEmbedder
from rag_core.knowledge.domain.fingerprint import (
    MinHasher,
    containment,
    jaccard,
    tokens,
)

DUPLICATE_SCORE = 0.60
DUPLICATE_MIN_TEXT = 0.45
RELATED_SCORE = 0.25

TEXT_WEIGHT = 0.6
META_WEIGHT = 0.4
META_WEIGHTS = {"nodes": 0.35, "documents": 0.30, "category": 0.15, "contract": 0.20}

STOPWORDS = frozenset(
    """
    the a an and or of to in on for with by from at is are was were be been this that these those it its as
    not no but into than then also only must may can should will has have had which who whom whose about
    after before under over between per via each all any other same new issue issues sub
    و در به از که این آن با برای را تا یا هم نیز است هست بود شد شده شود می کند کرد باید نباید هر
    یک دو سه بر اما اگر چون پس ها های ای ی خود ما شما آنها ایشان نیست هستند بودن کردن شدن
    بهدلیل دلیل بیشتر کمتر هنگام میشود میشوند میکند میکنند کرده کردهاند شدهاست دارد دارند داشت
    دهد میدهد میدهند خواهد بوده باشد همچنان حالی وقتی زمانی
    """.split()
)
_FA_PLURALS = ("های", "ها")


def content_tokens(text: str) -> frozenset[str]:
    """Normalized content tokens; deterministic and language-agnostic."""
    out: set[str] = set()
    for tok in tokens(text):
        if tok in STOPWORDS or len(tok) < 2 or tok.isdigit():
            continue
        for suffix in _FA_PLURALS:
            if tok.endswith(suffix) and len(tok) - len(suffix) >= 3:
                tok = tok[: -len(suffix)]
                break
        if (
            tok.isascii()
            and tok.endswith("s")
            and len(tok) > 4
            and not tok.endswith("ss")
        ):
            tok = tok[:-1]
        out.add(tok)
    return frozenset(out)


class MatchLabel(StrEnum):
    DUPLICATE = "duplicate"
    RELATED = "related"
    NEW = "new"


@dataclass(frozen=True)
class IssueProfile:
    """What comparison looks at; built from an Issue, a SubIssue or raw input."""

    key: str
    kind: str  # "issue" | "sub_issue"
    text: str
    nodes: frozenset[str]
    documents: frozenset[str]
    category: str | None
    contract: str | None
    status: str = ""
    title: str = ""
    texts: tuple[str, ...] = ()  # per-language texts; defaults to (text,)
    canonical: str | None = None  # duplicate_of target for closed duplicates

    def language_texts(self) -> tuple[str, ...]:
        return tuple(x for x in self.texts if x.strip()) or (self.text,)

    @classmethod
    def of_issue(cls, issue: Issue) -> IssueProfile:
        canonical = (
            str(issue.duplicate_of)
            if issue.duplicate_of and issue.status.is_done
            else None
        )
        return cls(
            key=str(issue.identifier),
            kind="issue",
            text=issue.text,
            texts=(
                " ".join(x for x in (issue.title, issue.description) if x),
                " ".join(x for x in (issue.title_fa, issue.description_fa) if x),
            ),
            canonical=canonical,
            nodes=frozenset(str(n) for n in issue.nodes),
            documents=frozenset(str(d) for d in issue.related_documents),
            category=issue.category.value,
            contract=str(issue.contract_ref) if issue.contract_ref else None,
            status=issue.status.value,
            title=issue.title,
        )

    @classmethod
    def of_subissue(cls, parent: Issue, sub: SubIssue) -> IssueProfile:
        return cls(
            key=str(sub.identifier),
            kind="sub_issue",
            text=" ".join(
                p for p in (sub.title, sub.title_fa, sub.scope, parent.customer) if p
            ),
            texts=(
                " ".join(p for p in (sub.title, sub.scope, parent.customer) if p),
                " ".join(p for p in (sub.title_fa, parent.title_fa) if p),
            ),
            nodes=frozenset(str(n) for n in sub.nodes),
            documents=frozenset(str(d) for d in sub.related_documents),
            category=None,
            contract=str(parent.contract_ref) if parent.contract_ref else None,
            status=sub.status.value,
            title=sub.title,
        )


@dataclass(frozen=True)
class ScoreBreakdown:
    text_jaccard: float
    text_containment: float
    text: float
    nodes: float | None
    documents: float | None
    category: float | None
    contract: float | None
    meta: float
    semantic: float | None
    score: float


@dataclass(frozen=True)
class Candidate:
    key: str
    kind: str
    title: str
    status: str
    label: MatchLabel
    breakdown: ScoreBreakdown
    shared_nodes: tuple[str, ...]
    shared_documents: tuple[str, ...]
    via: str | None = None  # a folded duplicate record that scored higher

    @property
    def score(self) -> float:
        return self.breakdown.score


@dataclass(frozen=True)
class ComparisonResult:
    query_key: str
    label: MatchLabel
    candidates: tuple[Candidate, ...]

    @property
    def best(self) -> Candidate | None:
        return self.candidates[0] if self.candidates else None

    def by_label(self, label: MatchLabel) -> list[Candidate]:
        return [c for c in self.candidates if c.label is label]


@dataclass
class ComparisonConfig:
    duplicate_score: float = DUPLICATE_SCORE
    duplicate_min_text: float = DUPLICATE_MIN_TEXT
    related_score: float = RELATED_SCORE
    include_subissues: bool = True
    top_k: int = 10
    prefilter_min_candidates: int = 200
    prefilter_threshold: float = 0.05
    meta_weights: dict[str, float] = field(default_factory=lambda: dict(META_WEIGHTS))


def _set_overlap(a: frozenset[str], b: frozenset[str]) -> float | None:
    """Overlap coefficient; ``None`` when both sides are empty (field skipped)."""
    if not a and not b:
        return None
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def _equal(a: str | None, b: str | None) -> float | None:
    if a is None and b is None:
        return None
    return 1.0 if a is not None and a == b else 0.0


def _cosine(u: list[float], v: list[float]) -> float:
    nu = math.sqrt(sum(x * x for x in u))
    nv = math.sqrt(sum(x * x for x in v))
    if not nu or not nv:
        return 0.0
    return max(0.0, min(1.0, sum(x * y for x, y in zip(u, v)) / (nu * nv)))


class IssueComparator:
    def __init__(
        self,
        config: ComparisonConfig | None = None,
        embedder: TextEmbedder | None = None,
    ) -> None:
        self.config = config or ComparisonConfig()
        self.embedder = embedder
        self._minhash = MinHasher(num_perm=64)

    # ------------------------------------------------------------ scoring
    def score(
        self, query: IssueProfile, other: IssueProfile, semantic: float | None = None
    ) -> ScoreBreakdown:
        tq = content_tokens(query.text)
        tj = tc = text = 0.0
        for candidate_text in other.language_texts():
            to = content_tokens(candidate_text)
            if not tq or not to:
                continue
            j, c = jaccard(tq, to), containment(tq, to)
            if 0.5 * j + 0.5 * c > text:
                tj, tc, text = j, c, 0.5 * j + 0.5 * c
        parts = {
            "nodes": _set_overlap(query.nodes, other.nodes),
            "documents": _set_overlap(query.documents, other.documents),
            "category": _equal(query.category, other.category)
            if query.category and other.category
            else None,
            "contract": _equal(query.contract, other.contract),
        }
        weights = {
            k: w for k, w in self.config.meta_weights.items() if parts[k] is not None
        }
        total = sum(weights.values())
        meta = sum(weights[k] * parts[k] for k in weights) / total if total else 0.0  # type: ignore[operator]
        if semantic is None:
            score = TEXT_WEIGHT * text + META_WEIGHT * meta
        else:
            score = 0.45 * text + 0.20 * semantic + 0.35 * meta
        r = lambda x: None if x is None else round(x, 4)  # noqa: E731
        return ScoreBreakdown(
            round(tj, 4),
            round(tc, 4),
            round(text, 4),
            r(parts["nodes"]),
            r(parts["documents"]),
            r(parts["category"]),
            r(parts["contract"]),
            round(meta, 4),
            r(semantic),
            round(score, 4),
        )

    def label(self, b: ScoreBreakdown) -> MatchLabel:
        if (
            b.score >= self.config.duplicate_score
            and b.text >= self.config.duplicate_min_text
        ):
            return MatchLabel.DUPLICATE
        if b.score >= self.config.related_score:
            return MatchLabel.RELATED
        return MatchLabel.NEW

    # ------------------------------------------------------------ public
    def profiles(self, existing: list[Issue]) -> list[IssueProfile]:
        out: list[IssueProfile] = []
        for issue in sorted(existing, key=lambda i: i.identifier.value):
            out.append(IssueProfile.of_issue(issue))
            if self.config.include_subissues:
                out.extend(IssueProfile.of_subissue(issue, s) for s in issue.subissues)
        return out

    def compare(
        self, query: Issue | IssueProfile, existing: list[Issue]
    ) -> ComparisonResult:
        q = query if isinstance(query, IssueProfile) else IssueProfile.of_issue(query)
        pool = [
            p
            for p in self.profiles(existing)
            if p.key != q.key and not p.key.startswith(q.key + "/")
        ]
        pool = self._prefilter(q, pool)
        semantic: dict[str, float] = {}
        if self.embedder is not None and pool:
            vectors = self.embedder.embed([q.text] + [p.text for p in pool])
            semantic = {
                p.key: _cosine(vectors[0], v) for p, v in zip(pool, vectors[1:])
            }
        by_key: dict[str, Candidate] = {}
        folded: list[tuple[IssueProfile, Candidate]] = []
        for p in pool:
            b = self.score(q, p, semantic.get(p.key) if semantic else None)
            cand = Candidate(
                key=p.key,
                kind=p.kind,
                title=p.title,
                status=p.status,
                label=self.label(b),
                breakdown=b,
                shared_nodes=tuple(sorted(q.nodes & p.nodes)),
                shared_documents=tuple(sorted(q.documents & p.documents)),
            )
            if p.canonical:
                folded.append((p, cand))
            else:
                by_key[p.key] = cand
        for p, cand in folded:
            target = by_key.get(p.canonical or "")
            if target is None:
                by_key[p.key] = cand
            elif cand.score > target.score:
                by_key[target.key] = Candidate(
                    key=target.key,
                    kind=target.kind,
                    title=target.title,
                    status=target.status,
                    label=cand.label,
                    breakdown=cand.breakdown,
                    shared_nodes=target.shared_nodes,
                    shared_documents=target.shared_documents,
                    via=p.key,
                )
        candidates = list(by_key.values())
        candidates.sort(key=lambda c: (-c.score, c.kind != "issue", c.key))
        top = tuple(candidates[: self.config.top_k])
        label = top[0].label if top else MatchLabel.NEW
        return ComparisonResult(q.key, label, top)

    def _prefilter(
        self, q: IssueProfile, pool: list[IssueProfile]
    ) -> list[IssueProfile]:
        """MinHash prefilter for large registries; metadata overlap always keeps a candidate."""
        if len(pool) < self.config.prefilter_min_candidates:
            return pool
        sig_q = self._minhash.signature(content_tokens(q.text))
        kept = []
        for p in pool:
            est = MinHasher.estimate(
                sig_q, self._minhash.signature(content_tokens(p.text))
            )
            if (
                est >= self.config.prefilter_threshold
                or q.nodes & p.nodes
                or q.documents & p.documents
            ):
                kept.append(p)
        return kept
