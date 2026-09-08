"""Unit tests for Reciprocal Rank Fusion with hand-calculated expectations."""

import uuid

from app.retrieval.hybrid import reciprocal_rank_fusion

A = uuid.UUID("00000000-0000-0000-0000-0000000000aa")
B = uuid.UUID("00000000-0000-0000-0000-0000000000bb")
C = uuid.UUID("00000000-0000-0000-0000-0000000000cc")
D = uuid.UUID("00000000-0000-0000-0000-0000000000dd")


def test_rrf_scores_match_hand_calculation():
    # A: 1/(60+1) + 1/(60+2); B: 1/(60+2) + 1/(60+1); equal -> tie broken by UUID.
    fused = reciprocal_rank_fusion([[A, B], [B, A]])
    scores = dict(fused)
    assert abs(scores[A] - (1 / 61 + 1 / 62)) < 1e-12
    assert abs(scores[B] - (1 / 62 + 1 / 61)) < 1e-12
    # A and B tie; deterministic order by str(uuid): 'aa' < 'bb'.
    assert [cid for cid, _ in fused] == [A, B]


def test_rrf_rewards_top_ranks():
    fused = reciprocal_rank_fusion([[A, B, C], [A, C, B]])
    # A is rank 1 in both lists -> highest.
    assert fused[0][0] == A


def test_rrf_handles_disjoint_lists_and_duplicates():
    fused = reciprocal_rank_fusion([[A, B], [C, D], [A]])
    scores = dict(fused)
    assert abs(scores[A] - (1 / 61 + 1 / 61)) < 1e-12  # rank 1 in list 1 and list 3
    assert set(scores) == {A, B, C, D}


def test_rrf_empty():
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[], []]) == []
