"""Cosine index and Reciprocal Rank Fusion."""

import math

import pytest

from rag_core.rag.domain.fusion import DEFAULT_RRF_K, reciprocal_rank_fusion
from rag_core.rag.domain.vector import InMemoryVectorIndex, cosine, l2_normalize
from rag_core.shared_kernel.errors import InvariantError

pytestmark = [pytest.mark.rag, pytest.mark.retrieval]


def test_normalize_and_cosine() -> None:
    v = l2_normalize([3.0, 4.0])
    assert math.isclose(v[0], 0.6, rel_tol=1e-6) and math.isclose(
        v[1], 0.8, rel_tol=1e-6
    )
    assert math.isclose(cosine([1, 0], [1, 0]), 1.0, rel_tol=1e-6)
    assert math.isclose(cosine([1, 0], [0, 1]), 0.0, abs_tol=1e-6)


def test_zero_vector_rejected() -> None:
    with pytest.raises(InvariantError):
        l2_normalize([0.0, 0.0])


def test_cosine_dim_mismatch() -> None:
    with pytest.raises(InvariantError):
        cosine([1, 0], [1, 0, 0])


def test_index_search_orders_by_similarity_and_respects_allowed() -> None:
    idx = InMemoryVectorIndex()
    idx.upsert("a", [1, 0, 0])
    idx.upsert("b", [0.7, 0.7, 0])
    idx.upsert("c", [0, 0, 1])
    assert [k for k, _ in idx.search([1, 0, 0], 3)] == ["a", "b", "c"]
    assert [k for k, _ in idx.search([1, 0, 0], 3, allowed=["c", "b"])] == ["b", "c"]
    assert idx.search([1, 0, 0], 3, allowed=[]) == []


def test_index_dim_fixed_by_first_vector() -> None:
    idx = InMemoryVectorIndex()
    idx.upsert("a", [1, 0])
    assert idx.dim == 2
    with pytest.raises(InvariantError):
        idx.upsert("b", [1, 0, 0])
    with pytest.raises(InvariantError):
        idx.search([1, 0, 0], 1)


def test_index_upsert_replaces_and_remove() -> None:
    idx = InMemoryVectorIndex()
    idx.upsert("a", [1, 0])
    idx.upsert("a", [0, 1])
    assert len(idx) == 1 and idx.search([0, 1], 1)[0][1] > 0.99
    idx.remove("a")
    idx.remove("a")
    assert idx.keys() == set() and idx.search([0, 1], 1) == []


def test_rrf_formula() -> None:
    fused = dict(reciprocal_rank_fusion({"lex": ["a", "b"], "vec": ["b", "c"]}, k=60))
    assert math.isclose(fused["a"], 1 / 61)
    assert math.isclose(fused["b"], 1 / 62 + 1 / 61)
    assert math.isclose(fused["c"], 1 / 62)


def test_rrf_rewards_agreement() -> None:
    fused = reciprocal_rank_fusion({"lex": ["a", "b", "c"], "vec": ["c", "b", "a"]})
    assert fused[0][0] == "b" or fused[0][1] == fused[1][1]
    # b is second in both lists; a and c are first in one and third in the other
    scores = dict(fused)
    assert math.isclose(scores["a"], scores["c"])


def test_rrf_weights() -> None:
    fused = reciprocal_rank_fusion(
        {"lex": ["a"], "vec": ["b"]}, weights={"lex": 1.0, "vec": 2.0}
    )
    assert fused[0][0] == "b"


def test_rrf_ignores_repeated_keys_in_one_ranking() -> None:
    fused = dict(reciprocal_rank_fusion({"lex": ["a", "a", "b"]}, k=60))
    assert math.isclose(fused["b"], 1 / 62)


def test_rrf_deterministic_ties_and_validation() -> None:
    assert [k for k, _ in reciprocal_rank_fusion({"x": ["b"], "y": ["a"]})] == [
        "a",
        "b",
    ]
    assert DEFAULT_RRF_K == 60
    with pytest.raises(ValueError):
        reciprocal_rank_fusion({"x": ["a"]}, k=0)
    assert reciprocal_rank_fusion({}) == []
