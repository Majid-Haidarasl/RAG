"""Duplicate, near-duplicate and overlap detection (pure Python, stdlib only).

Rules (see docs/phase-05/versioning-and-dedup.md):

* Pairs from the **same source file** are never compared (chunk overlap
  inside one file is created by the chunker on purpose).
* A **bilingual pair** — same document id, different language — is never a
  duplicate. Such candidates are counted in ``bilingual_pairs_excluded``.
* Exact duplicate: identical normalized-text hash, text at least
  ``min_exact_chars`` long after normalization.
* Near duplicate: word-3-shingle Jaccard ≥ ``near_threshold``. Candidates
  come from MinHash + LSH banding and are always verified with exact Jaccard.
* Overlap / containment: one side's shingles are ≥ ``containment_threshold``
  contained in the other, but the pair is not exact/near. Candidates come
  from an inverted shingle index that ignores boilerplate shingles.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from itertools import combinations
import time

from rag_core.knowledge.domain.fingerprint import (
    MinHasher,
    containment,
    jaccard,
    lsh_buckets,
    normalize_for_hash,
    normalized_hash,
    shingles,
)


@dataclass(frozen=True)
class TextRecord:
    """One comparable unit: a chunk or a whole document rendition."""

    key: str
    document_id: str
    language: str | None
    source: str
    text: str
    version: str = ""
    file_format: str = ""


@dataclass(frozen=True)
class DedupConfig:
    shingle_k: int = 3
    num_perm: int = 64
    bands: int = 16  # 16 bands x 4 rows -> LSH threshold ~ (1/16)^(1/4) ~ 0.50
    near_threshold: float = 0.80
    containment_threshold: float = 0.60
    min_exact_chars: int = 30
    min_shingles: int = 8
    boilerplate_source_fraction: float = 0.25
    boilerplate_min_sources: int = 5
    seed: int = 1405


@dataclass
class PairFinding:
    left: str
    right: str
    kind: str
    jaccard: float
    containment: float = 0.0
    contained: str = ""
    left_doc: str = ""
    right_doc: str = ""
    scope: str = "cross_document"  # or "rendition"

    def to_dict(self) -> dict[str, object]:
        return {
            "scope": self.scope,
            "left": self.left,
            "right": self.right,
            "kind": self.kind,
            "jaccard": round(self.jaccard, 4),
            "containment": round(self.containment, 4),
            "contained": self.contained,
            "left_doc": self.left_doc,
            "right_doc": self.right_doc,
        }


@dataclass(frozen=True)
class ExactGroup:
    members: tuple[str, ...]
    documents: tuple[str, ...]
    scope: str  # "rendition" (one doc+language, several formats) or "cross_document"

    def to_dict(self) -> dict[str, object]:
        return {"scope": self.scope, "documents": list(self.documents), "members": list(self.members)}


@dataclass
class DedupReport:
    records: int
    exact_groups: list[ExactGroup] = field(default_factory=list)
    near_pairs: list[PairFinding] = field(default_factory=list)
    overlap_pairs: list[PairFinding] = field(default_factory=list)
    bilingual_pairs_excluded: int = 0
    bilingual_candidates_seen: int = 0
    bilingual_excluded_by_rule: dict[str, int] = field(default_factory=dict)
    lsh_candidates: int = 0
    reference_near_pairs: int = 0
    timings_s: dict[str, float] = field(default_factory=dict)

    @property
    def lsh_recall(self) -> float | None:
        if self.reference_near_pairs == 0:
            return None
        return len(self.near_pairs) / self.reference_near_pairs

    def count_by_scope(self) -> dict[str, dict[str, int]]:
        def tally(scopes: list[str]) -> dict[str, int]:
            return {s: scopes.count(s) for s in ("rendition", "cross_document")}

        return {
            "exact_groups": tally([g.scope for g in self.exact_groups]),
            "near_pairs": tally([p.scope for p in self.near_pairs]),
            "overlap_pairs": tally([p.scope for p in self.overlap_pairs]),
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "records": self.records,
            "by_scope": self.count_by_scope(),
            "exact_groups": [g.to_dict() for g in self.exact_groups],
            "exact_group_count": len(self.exact_groups),
            "near_pairs": [p.to_dict() for p in self.near_pairs],
            "near_pair_count": len(self.near_pairs),
            "overlap_pairs": [p.to_dict() for p in self.overlap_pairs],
            "overlap_pair_count": len(self.overlap_pairs),
            "bilingual_pairs_excluded": self.bilingual_pairs_excluded,
            "bilingual_excluded_by_rule": self.bilingual_excluded_by_rule,
            "bilingual_candidates_seen": self.bilingual_candidates_seen,
            "lsh_candidates": self.lsh_candidates,
            "reference_near_pairs": self.reference_near_pairs,
            "lsh_recall": self.lsh_recall,
            "timings_s": {k: round(v, 3) for k, v in self.timings_s.items()},
        }


def _pair(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def pair_scope(a: TextRecord, b: TextRecord) -> str:
    return "rendition" if a.document_id == b.document_id and a.language == b.language else "cross_document"


def is_bilingual_pair(a: TextRecord, b: TextRecord) -> bool:
    return (
        a.document_id == b.document_id
        and a.language is not None
        and b.language is not None
        and a.language != b.language
    )


class DuplicateFinder:
    def __init__(self, config: DedupConfig | None = None) -> None:
        self.config = config or DedupConfig()
        self._hasher = MinHasher(self.config.num_perm, self.config.seed)

    def find(self, records: list[TextRecord]) -> DedupReport:
        cfg = self.config
        report = DedupReport(records=len(records))
        t0 = time.perf_counter()
        by_key = {r.key: r for r in records}
        if len(by_key) != len(records):
            raise ValueError("record keys must be unique")
        norm = {r.key: normalize_for_hash(r.text) for r in records}
        hashes = {r.key: normalized_hash(r.text) for r in records}
        sh = {r.key: shingles(r.text, cfg.shingle_k) for r in records}
        report.timings_s["fingerprint"] = time.perf_counter() - t0

        bilingual_candidates: set[tuple[str, str]] = set()
        bilingual_excluded: dict[tuple[str, str], str] = {}

        def blocked(a: TextRecord, b: TextRecord) -> str | None:
            if a.source == b.source:
                return "same_source"
            if is_bilingual_pair(a, b):
                bilingual_candidates.add(_pair(a.key, b.key))
                return "bilingual"
            return None

        def exclude_bilingual(a: TextRecord, b: TextRecord, rule: str) -> None:
            bilingual_excluded.setdefault(_pair(a.key, b.key), rule)

        # ---------------- exact
        t1 = time.perf_counter()
        groups: dict[str, list[TextRecord]] = defaultdict(list)
        for r in records:
            if len(norm[r.key]) >= cfg.min_exact_chars:
                groups[hashes[r.key]].append(r)
        exact_pairs: set[tuple[str, str]] = set()
        for members in groups.values():
            if len(members) < 2:
                continue
            keep: set[str] = set()
            for a, b in combinations(members, 2):
                why = blocked(a, b)
                if why == "bilingual":
                    exclude_bilingual(a, b, "exact")
                if why is None:
                    keep.update((a.key, b.key))
                    exact_pairs.add(_pair(a.key, b.key))
            if keep:
                members = sorted(keep)
                docs = sorted({by_key[k].document_id for k in members})
                langs = {by_key[k].language for k in members}
                scope = "rendition" if len(docs) == 1 and len(langs) == 1 else "cross_document"
                report.exact_groups.append(ExactGroup(tuple(members), tuple(docs), scope))
        report.exact_groups.sort(key=lambda g: g.members)
        report.timings_s["exact"] = time.perf_counter() - t1

        eligible = [r for r in records if len(sh[r.key]) >= cfg.min_shingles]

        # ---------------- near (MinHash + LSH, verified)
        t2 = time.perf_counter()
        sigs = {r.key: self._hasher.signature(sh[r.key]) for r in eligible}
        buckets: dict[tuple[int, tuple[int, ...]], list[str]] = defaultdict(list)
        for r in eligible:
            for bucket in lsh_buckets(sigs[r.key], cfg.bands):
                buckets[bucket].append(r.key)
        candidates: set[tuple[str, str]] = set()
        for keys in buckets.values():
            if len(keys) < 2:
                continue
            for a, b in combinations(sorted(set(keys)), 2):
                candidates.add((a, b))
        report.lsh_candidates = len(candidates)
        near_set: set[tuple[str, str]] = set()
        for a_key, b_key in sorted(candidates):
            a, b = by_key[a_key], by_key[b_key]
            if (a_key, b_key) in exact_pairs:
                continue
            why = blocked(a, b)
            if why == "same_source":
                continue
            j = jaccard(sh[a_key], sh[b_key])
            if j >= cfg.near_threshold and why == "bilingual":
                exclude_bilingual(a, b, "near")
                continue
            if j >= cfg.near_threshold:
                near_set.add((a_key, b_key))
                report.near_pairs.append(
                    PairFinding(
                        a_key, b_key, "near", j,
                        left_doc=a.document_id, right_doc=b.document_id, scope=pair_scope(a, b),
                    )
                )
        report.timings_s["near_minhash_lsh"] = time.perf_counter() - t2

        # ---------------- overlap (inverted index, boilerplate filtered)
        t3 = time.perf_counter()
        sources = {r.source for r in records}
        max_sources = max(cfg.boilerplate_min_sources, int(cfg.boilerplate_source_fraction * len(sources)))
        postings: dict[str, list[str]] = defaultdict(list)
        for r in eligible:
            for s in sh[r.key]:
                postings[s].append(r.key)
        shared: dict[tuple[str, str], int] = defaultdict(int)
        for s, keys in postings.items():
            if len(keys) < 2:
                continue
            if len({by_key[k].source for k in keys}) > max_sources:
                continue  # boilerplate shingle (headers, version lines)
            for a, b in combinations(sorted(keys), 2):
                shared[(a, b)] += 1
        reference_near = 0
        for (a_key, b_key), count in sorted(shared.items()):
            a, b = by_key[a_key], by_key[b_key]
            why = blocked(a, b)
            if why == "same_source" or (a_key, b_key) in exact_pairs:
                continue
            sa, sb = sh[a_key], sh[b_key]
            j = jaccard(sa, sb)
            if j >= cfg.near_threshold:
                if why is None:
                    reference_near += 1
                continue
            small, big, small_key = (sa, sb, a_key) if len(sa) <= len(sb) else (sb, sa, b_key)
            c = containment(small, big)
            if c >= cfg.containment_threshold and why == "bilingual":
                exclude_bilingual(a, b, "overlap")
                continue
            if c >= cfg.containment_threshold:
                report.overlap_pairs.append(
                    PairFinding(
                        a_key,
                        b_key,
                        "overlap",
                        j,
                        containment=c,
                        contained=small_key,
                        left_doc=a.document_id,
                        right_doc=b.document_id,
                        scope=pair_scope(a, b),
                    )
                )
        report.reference_near_pairs = reference_near
        report.timings_s["overlap_index"] = time.perf_counter() - t3
        report.bilingual_pairs_excluded = len(bilingual_excluded)
        report.bilingual_candidates_seen = len(bilingual_candidates)
        report.bilingual_excluded_by_rule = {
            rule: sum(1 for r in bilingual_excluded.values() if r == rule) for rule in ("exact", "near", "overlap")
        }
        report.timings_s["total"] = time.perf_counter() - t0
        return report
