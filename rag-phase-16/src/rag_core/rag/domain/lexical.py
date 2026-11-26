"""BM25 over Persian-normalized tokens (stdlib only).

Tokens come from the Phase 5 fingerprint normalizer (NFKC, Arabic yeh/kaf →
Persian, Persian digits → Latin, ZWNJ removed, punctuation stripped), so
``می‌شود`` / ``میشود`` and ``۲۶`` / ``26`` match. A short FA/EN stopword list
and a light plural strip keep scores focused on content words.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from rag_core.knowledge.domain.fingerprint import tokens as normalized_tokens

STOPWORDS_FA = frozenset(
    ["و", "در", "به", "از", "که", "این", "آن", "با", "را", "برای", "تا", "یا", "هر", "هم", "نیز", "اما", "اگر", "چه", "چون", "بر", "پس", "بی", "است", "هست", "بود", "شد", "شود", "میشود", "می", "شده", "باشد", "کند", "کرد", "کرده", "کنند", "دارد", "داشت", "دارند", "یک", "ها", "های", "ای", "اند", "ام", "ایم", "اید", "ی", "من", "تو", "او", "ما", "شما", "آنها", "ایشان", "خود", "چند", "چقدر", "چیست", "کدام", "چگونه", "چطور", "کجا", "کی", "چرا", "آیا", "طبق", "مورد", "درباره", "بین", "روی", "زیر", "پیش", "بعد", "قبل"]
)
STOPWORDS_EN = frozenset(
    ["a", "an", "the", "and", "or", "of", "in", "on", "at", "to", "for", "from", "by", "with", "as", "is", "are", "was", "were", "be", "been", "being", "it", "its", "this", "that", "these", "those", "what", "which", "who", "whom", "how", "why", "when", "where", "does", "do", "did", "can", "could", "should", "would", "will", "shall", "may", "might", "must", "has", "have", "had", "not", "no", "than", "then", "there", "their", "they", "them", "we", "you", "your", "our", "i", "he", "she", "his", "her", "about", "into", "under", "over", "per", "any", "all", "each", "such"]
)
STOPWORDS = STOPWORDS_FA | STOPWORDS_EN

_FA_SUFFIXES = ("های", "ها")
_EN_SUFFIXES = ("ies", "es", "s")


def _stem(tok: str) -> str:
    if tok.isdigit():
        return tok
    if "\u0600" <= tok[0] <= "\u06ff":
        for suf in _FA_SUFFIXES:
            if tok.endswith(suf) and len(tok) - len(suf) >= 3:
                return tok[: -len(suf)]
        return tok
    for suf in _EN_SUFFIXES:
        if tok.endswith(suf) and len(tok) - len(suf) >= 3:
            return tok[: -len(suf)] + ("y" if suf == "ies" else "")
    return tok


def lexical_tokens(text: str) -> list[str]:
    out: list[str] = []
    for tok in normalized_tokens(text):
        if tok in STOPWORDS:
            continue
        if len(tok) < 2 and not tok.isdigit():
            continue
        out.append(_stem(tok))
    return out


@dataclass(frozen=True)
class Bm25Config:
    k1: float = 1.2
    b: float = 0.75


class Bm25Index:
    """Okapi BM25 with the non-negative idf ``ln(1 + (N - df + .5)/(df + .5))``."""

    def __init__(
        self,
        documents: Iterable[tuple[str, str]] = (),
        config: Bm25Config | None = None,
    ) -> None:
        self.config = config or Bm25Config()
        self._tf: dict[str, Counter[str]] = {}
        self._len: dict[str, int] = {}
        self._df: Counter[str] = Counter()
        for key, text in documents:
            self.add(key, text)

    def add(self, key: str, text: str) -> None:
        if key in self._tf:
            self.remove(key)
        tf = Counter(lexical_tokens(text))
        self._tf[key] = tf
        self._len[key] = sum(tf.values())
        self._df.update(tf.keys())

    def remove(self, key: str) -> None:
        tf = self._tf.pop(key, None)
        if tf is None:
            return
        self._len.pop(key, None)
        for term in tf:
            self._df[term] -= 1
            if self._df[term] <= 0:
                del self._df[term]

    def __len__(self) -> int:
        return len(self._tf)

    def __contains__(self, key: str) -> bool:
        return key in self._tf

    def idf(self, term: str) -> float:
        n = len(self._tf)
        df = self._df.get(term, 0)
        return math.log(1.0 + (n - df + 0.5) / (df + 0.5))

    def search(
        self, query: str, k: int, allowed: Iterable[str] | None = None
    ) -> list[tuple[str, float]]:
        terms = list(dict.fromkeys(lexical_tokens(query)))
        if not terms or not self._tf:
            return []
        keys = (
            self._tf.keys()
            if allowed is None
            else [a for a in allowed if a in self._tf]
        )
        avg = (sum(self._len.values()) / len(self._len)) or 1.0
        k1, b = self.config.k1, self.config.b
        idfs = {t: self.idf(t) for t in terms if t in self._df}
        if not idfs:
            return []
        scored: list[tuple[str, float]] = []
        for key in keys:
            tf = self._tf[key]
            norm = k1 * (1 - b + b * self._len[key] / avg)
            score = 0.0
            for term, idf in idfs.items():
                f = tf.get(term, 0)
                if f:
                    score += idf * f * (k1 + 1) / (f + norm)
            if score > 0:
                scored.append((key, score))
        scored.sort(key=lambda kv: (-kv[1], kv[0]))
        return scored[:k]
