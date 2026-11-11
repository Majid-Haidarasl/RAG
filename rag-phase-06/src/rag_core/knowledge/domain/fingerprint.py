"""Text fingerprints for exact and near-duplicate detection (stdlib only).

Normalization for hashing is deliberately aggressive: it should treat two
renderings of the same sentence (DOCX vs PDF line breaks, ZWNJ vs space,
Persian vs Latin digits, Arabic vs Persian yeh/kaf) as identical text.
"""

from __future__ import annotations

from hashlib import blake2b, sha256
import random
import unicodedata

from rag_core.shared_kernel.numerals import normalize_digits
from rag_core.shared_kernel.persian import normalize_yeh_kaf

ZWNJ = "\u200c"
TATWEEL = "\u0640"
_INVISIBLES = {ZWNJ, "\u200d", "\u200e", "\u200f", "\ufeff", TATWEEL}


def _clean_chars(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = normalize_digits(normalize_yeh_kaf(text)).lower()
    out: list[str] = []
    for ch in text:
        if ch in _INVISIBLES:
            continue  # "می‌رود" == "میرود"
        cat = unicodedata.category(ch)
        if cat == "Mn":  # Arabic diacritics (harakat)
            continue
        if cat[0] in {"P", "S"}:  # punctuation, symbols (|, ٬, ، , ...)
            out.append(" ")
            continue
        out.append(ch)
    return "".join(out)


def tokens(text: str) -> list[str]:
    return _clean_chars(text).split()


def normalize_for_hash(text: str) -> str:
    """Whitespace-free canonical form. ``می رود`` == ``می‌رود`` == ``میرود``."""
    return "".join(tokens(text))


def normalized_hash(text: str) -> str:
    return sha256(normalize_for_hash(text).encode("utf-8")).hexdigest()


def shingles(text: str, k: int = 3) -> frozenset[str]:
    """Word k-shingles. Texts shorter than k words give one shingle."""
    toks = tokens(text)
    if not toks:
        return frozenset()
    if len(toks) < k:
        return frozenset({" ".join(toks)})
    return frozenset(" ".join(toks[i : i + k]) for i in range(len(toks) - k + 1))


def char_shingles(text: str, k: int = 5) -> frozenset[str]:
    """Whitespace-insensitive character k-grams of the hash-normalized text.

    Robust to spurious or missing spaces (Arabic-script PDF extraction), so it
    is used for document-level rendition matching.
    """
    norm = normalize_for_hash(text)
    if not norm:
        return frozenset()
    if len(norm) < k:
        return frozenset({norm})
    return frozenset(norm[i : i + k] for i in range(len(norm) - k + 1))


def jaccard(a: frozenset[str] | set[str], b: frozenset[str] | set[str]) -> float:
    if not a and not b:
        return 1.0
    union = len(a | b)
    return len(a & b) / union if union else 0.0


def containment(a: frozenset[str] | set[str], b: frozenset[str] | set[str]) -> float:
    """Share of ``a`` that is contained in ``b``."""
    if not a:
        return 0.0
    return len(a & b) / len(a)


_MERSENNE = (1 << 61) - 1


def _hash64(s: str) -> int:
    return int.from_bytes(blake2b(s.encode("utf-8"), digest_size=8).digest(), "big")


class MinHasher:
    """Classic MinHash with ``num_perm`` universal hash permutations.

    Deterministic: the permutation coefficients come from a fixed seed, so
    signatures are reproducible across machines and runs.
    """

    def __init__(self, num_perm: int = 64, seed: int = 1405) -> None:
        if num_perm < 1:
            raise ValueError("num_perm must be >= 1")
        rng = random.Random(seed)
        self.num_perm = num_perm
        self._coeffs = [
            (rng.randrange(1, _MERSENNE), rng.randrange(0, _MERSENNE)) for _ in range(num_perm)
        ]

    def signature(self, shingle_set: frozenset[str] | set[str]) -> tuple[int, ...]:
        if not shingle_set:
            return tuple([_MERSENNE] * self.num_perm)
        hashes = [_hash64(s) for s in shingle_set]
        p = _MERSENNE
        return tuple(min((a * x + b) % p for x in hashes) for a, b in self._coeffs)

    @staticmethod
    def estimate(sig_a: tuple[int, ...], sig_b: tuple[int, ...]) -> float:
        if len(sig_a) != len(sig_b) or not sig_a:
            raise ValueError("signatures must have the same non-zero length")
        return sum(1 for x, y in zip(sig_a, sig_b) if x == y) / len(sig_a)


def lsh_buckets(signature: tuple[int, ...], bands: int) -> list[tuple[int, tuple[int, ...]]]:
    """Split a signature into ``bands`` bands; each (band, values) is a bucket key."""
    if bands < 1 or len(signature) % bands:
        raise ValueError("signature length must be divisible by bands")
    rows = len(signature) // bands
    return [(b, signature[b * rows : (b + 1) * rows]) for b in range(bands)]


def guess_language(text: str) -> str | None:
    """'fa' if Arabic-script letters dominate, 'en' if Latin dominates, else None.

    Used for derived renditions (PDF/DOC exports) whose path carries no
    language folder, so bilingual-pair exclusion still applies to them.
    """
    arabic = latin = 0
    for ch in text:
        if "\u0600" <= ch <= "\u06ff" or "\ufb50" <= ch <= "\ufeff":
            arabic += 1
        elif ch.isascii() and ch.isalpha():
            latin += 1
    total = arabic + latin
    if total < 20:
        return None
    if arabic / total >= 0.5:
        return "fa"
    return "en"
