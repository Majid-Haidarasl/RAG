"""Brute-force cosine index (stdlib ``array``; no numpy needed).

About 1.2k chunks × 1024 dims is ~1.2M multiply-adds per query, which takes
a fraction of a second in pure Python. Vectors are L2-normalized on insert,
so cosine is a plain dot product.
"""

from __future__ import annotations

import math
from array import array
from collections.abc import Iterable

from rag_core.shared_kernel.errors import InvariantError


def l2_normalize(vector: Iterable[float]) -> array:
    vec = array("f", vector)
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        raise InvariantError("zero vector cannot be indexed")
    return array("f", (x / norm for x in vec))


def cosine(a: Iterable[float], b: Iterable[float]) -> float:
    va, vb = l2_normalize(a), l2_normalize(b)
    if len(va) != len(vb):
        raise InvariantError("vector dimensions differ")
    return float(sum(x * y for x, y in zip(va, vb)))


class InMemoryVectorIndex:
    def __init__(self, dim: int | None = None) -> None:
        self.dim = dim
        self._vectors: dict[str, array] = {}

    def upsert(self, key: str, vector: list[float] | array) -> None:
        vec = l2_normalize(vector)
        if self.dim is None:
            self.dim = len(vec)
        if len(vec) != self.dim:
            raise InvariantError(f"vector dim {len(vec)} != index dim {self.dim}")
        self._vectors[key] = vec

    def remove(self, key: str) -> None:
        self._vectors.pop(key, None)

    def keys(self) -> set[str]:
        return set(self._vectors)

    def vector(self, key: str) -> array:
        return self._vectors[key]

    def __len__(self) -> int:
        return len(self._vectors)

    def search(
        self, vector: list[float], k: int, allowed: Iterable[str] | None = None
    ) -> list[tuple[str, float]]:
        if not self._vectors:
            return []
        q = l2_normalize(vector)
        if len(q) != self.dim:
            raise InvariantError(f"query dim {len(q)} != index dim {self.dim}")
        keys = (
            self._vectors.keys()
            if allowed is None
            else [a for a in allowed if a in self._vectors]
        )
        scored = [
            (key, float(sum(x * y for x, y in zip(q, self._vectors[key]))))
            for key in keys
        ]
        scored.sort(key=lambda kv: (-kv[1], kv[0]))
        return scored[:k]
