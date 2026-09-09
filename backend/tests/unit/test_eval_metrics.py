"""Unit tests for retrieval metrics with hand-calculated expectations."""

import math

from app.evals.metrics import hit_at_k, ndcg_at_k, recall_at_k, reciprocal_rank


def test_hit_at_k():
    assert hit_at_k([0, 1, 0], 5) == 1.0
    assert hit_at_k([0, 0, 0], 5) == 0.0
    assert hit_at_k([0, 0, 1], 2) == 0.0  # relevant is at rank 3, outside top-2
    assert hit_at_k([], 5) == 0.0


def test_recall_at_k():
    assert recall_at_k([1, 0, 1, 0], total_relevant=3, k=5) == 2 / 3
    assert recall_at_k([1, 1, 1], total_relevant=3, k=5) == 1.0
    assert recall_at_k([0, 0], total_relevant=0, k=5) == 0.0
    assert recall_at_k([1, 0], total_relevant=2, k=1) == 0.5


def test_reciprocal_rank():
    assert reciprocal_rank([0, 0, 1], 10) == 1 / 3
    assert reciprocal_rank([1, 0], 10) == 1.0
    assert reciprocal_rank([0, 0, 0], 10) == 0.0
    # First relevant beyond k is not counted.
    assert reciprocal_rank([0, 0, 0, 1], 3) == 0.0


def test_ndcg_perfect_ranking_is_one():
    assert ndcg_at_k([3, 2, 0], [3, 2, 0], 10) == 1.0


def test_ndcg_hand_calculation():
    # DCG([3,0,2]) = 7/log2(2) + 0/log2(3) + 3/log2(4) = 7 + 0 + 1.5 = 8.5
    # IDCG([3,2,0]) = 7/log2(2) + 3/log2(3) + 0 = 7 + 1.892789 = 8.892789
    expected = 8.5 / (7 + 3 / math.log2(3))
    assert abs(ndcg_at_k([3, 0, 2], [3, 2, 0], 10) - expected) < 1e-9


def test_ndcg_no_relevant_is_zero():
    assert ndcg_at_k([0, 0], [0, 0], 10) == 0.0
