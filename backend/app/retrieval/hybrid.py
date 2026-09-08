"""Reciprocal Rank Fusion (RRF).

Combines multiple ranked lists using rank positions (not incompatible raw scores). Ties are
broken deterministically by chunk UUID so repeated runs produce identical ordering.
"""

import uuid
from collections import defaultdict

RRF_K = 60


def reciprocal_rank_fusion(
    ranked_lists: list[list[uuid.UUID]], k: int = RRF_K
) -> list[tuple[uuid.UUID, float]]:
    scores: dict[uuid.UUID, float] = defaultdict(float)
    for ranked in ranked_lists:
        for rank, chunk_id in enumerate(ranked, start=1):
            scores[chunk_id] += 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], str(item[0])))
