"""Deterministic retrieval metrics.

Each function is pure and side-effect free so it can be unit-tested with hand calculations.
``ranked_relevances`` is the graded relevance (0-3) of each retrieved chunk, in rank order.
A chunk is "relevant" for Hit/Recall/MRR when its graded relevance is >= 1.
"""

import math

RELEVANT_THRESHOLD = 1


def hit_at_k(ranked_relevances: list[int], k: int) -> float:
    """1.0 if any relevant chunk appears in the top-k, else 0.0."""
    return 1.0 if any(rel >= RELEVANT_THRESHOLD for rel in ranked_relevances[:k]) else 0.0


def recall_at_k(ranked_relevances: list[int], total_relevant: int, k: int) -> float:
    """Fraction of all known-relevant chunks retrieved in the top-k."""
    if total_relevant <= 0:
        return 0.0
    found = sum(1 for rel in ranked_relevances[:k] if rel >= RELEVANT_THRESHOLD)
    return found / total_relevant


def reciprocal_rank(ranked_relevances: list[int], k: int = 10) -> float:
    """Reciprocal rank of the first relevant result within the top-k (0 if none)."""
    for index, rel in enumerate(ranked_relevances[:k], start=1):
        if rel >= RELEVANT_THRESHOLD:
            return 1.0 / index
    return 0.0


def _dcg(relevances: list[int], k: int) -> float:
    return sum(
        (2**rel - 1) / math.log2(rank + 1) for rank, rel in enumerate(relevances[:k], start=1)
    )


def ndcg_at_k(ranked_relevances: list[int], ideal_relevances: list[int], k: int) -> float:
    """Normalized DCG using graded relevance. ``ideal_relevances`` is every judged relevance
    for the case (used to build the ideal ranking)."""
    ideal = _dcg(sorted(ideal_relevances, reverse=True), k)
    if ideal == 0:
        return 0.0
    return _dcg(ranked_relevances, k) / ideal
