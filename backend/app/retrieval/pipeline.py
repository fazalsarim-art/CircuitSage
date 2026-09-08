"""Unified retrieval pipeline: lexical / dense / hybrid (RRF) / reranked_hybrid.

Produces the selected evidence plus a full per-candidate trace (stage ranks and scores)
so the chat layer can persist ``retrieval_results`` and explain every answer.
"""

import time
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.document import Chunk, Document
from app.db.models.enums import DocumentStatus
from app.db.models.user import User
from app.retrieval.dense import dense_search_ids
from app.retrieval.hybrid import reciprocal_rank_fusion
from app.retrieval.lexical import lexical_search_ids, visibility_clause
from app.retrieval.reranker import Reranker
from app.services.embeddings import Embedder
from app.services.vector_store import VectorStore

CANDIDATES_PER_SOURCE = 30
FUSION_KEEP = 20

_HYBRID_MODES = ("hybrid", "reranked_hybrid")


@dataclass
class RetrievalCandidate:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    ordinal: int
    page_start: int
    page_end: int
    content: str
    lexical_rank: int | None = None
    dense_rank: int | None = None
    fused_rank: int | None = None
    rerank_rank: int | None = None
    lexical_score: float | None = None
    dense_score: float | None = None
    fused_score: float | None = None
    rerank_score: float | None = None
    final_rank: int | None = None
    selected: bool = False


@dataclass
class RetrievalOutcome:
    mode: str
    candidates: list[RetrievalCandidate]
    selected: list[RetrievalCandidate]
    timings_ms: dict[str, float] = field(default_factory=dict)


def _hydrate(db: Session, user: User, chunk_ids: list[uuid.UUID]) -> dict:
    if not chunk_ids:
        return {}
    stmt = (
        select(
            Chunk.id,
            Chunk.document_id,
            Document.title,
            Chunk.ordinal,
            Chunk.page_start,
            Chunk.page_end,
            Chunk.content,
        )
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.id.in_(chunk_ids), Document.status == DocumentStatus.indexed)
    )
    clause = visibility_clause(user)
    if clause is not None:
        stmt = stmt.where(clause)
    return {row.id: row for row in db.execute(stmt).all()}


def run_retrieval(
    db: Session,
    user: User,
    query: str,
    mode: str,
    top_k: int,
    *,
    embedder: Embedder | None = None,
    vector_store: VectorStore | None = None,
    reranker: Reranker | None = None,
    document_ids: list[uuid.UUID] | None = None,
) -> RetrievalOutcome:
    timings: dict[str, float] = {}
    lexical_ids: list[tuple[uuid.UUID, float]] = []
    dense_ids: list[tuple[uuid.UUID, float]] = []

    if mode in ("lexical", *_HYBRID_MODES):
        limit = top_k if mode == "lexical" else CANDIDATES_PER_SOURCE
        start = time.perf_counter()
        lexical_ids = lexical_search_ids(db, user, query, limit, document_ids)
        timings["lexical"] = round((time.perf_counter() - start) * 1000, 2)

    if mode in ("dense", *_HYBRID_MODES):
        limit = top_k if mode == "dense" else CANDIDATES_PER_SOURCE
        start = time.perf_counter()
        dense_ids = dense_search_ids(vector_store, embedder, user, query, limit, document_ids)
        timings["dense"] = round((time.perf_counter() - start) * 1000, 2)

    lex_rank = {cid: i + 1 for i, (cid, _) in enumerate(lexical_ids)}
    lex_score = dict(lexical_ids)
    den_rank = {cid: i + 1 for i, (cid, _) in enumerate(dense_ids)}
    den_score = dict(dense_ids)
    fused_rank: dict[uuid.UUID, int] = {}
    fused_score: dict[uuid.UUID, float] = {}

    if mode == "lexical":
        ordered = [cid for cid, _ in lexical_ids]
    elif mode == "dense":
        ordered = [cid for cid, _ in dense_ids]
    else:
        start = time.perf_counter()
        fused = reciprocal_rank_fusion(
            [[cid for cid, _ in lexical_ids], [cid for cid, _ in dense_ids]]
        )
        timings["fusion"] = round((time.perf_counter() - start) * 1000, 2)
        fused = fused[:FUSION_KEEP]
        fused_score = dict(fused)
        ordered = [cid for cid, _ in fused]
        fused_rank = {cid: i + 1 for i, cid in enumerate(ordered)}

    rows = _hydrate(db, user, ordered)
    ordered = [cid for cid in ordered if cid in rows]

    rerank_rank: dict[uuid.UUID, int] = {}
    rerank_score: dict[uuid.UUID, float] = {}
    if mode == "reranked_hybrid" and reranker is not None and ordered:
        start = time.perf_counter()
        scores = reranker.rank(query, [rows[cid].content for cid in ordered])
        reranked = sorted(zip(ordered, scores, strict=True), key=lambda kv: (-kv[1], str(kv[0])))
        timings["rerank"] = round((time.perf_counter() - start) * 1000, 2)
        ordered = [cid for cid, _ in reranked]
        rerank_rank = {cid: i + 1 for i, cid in enumerate(ordered)}
        rerank_score = {cid: score for cid, score in reranked}

    selected_ids = set(ordered[:top_k])
    candidates: list[RetrievalCandidate] = []
    for index, cid in enumerate(ordered):
        row = rows[cid]
        candidates.append(
            RetrievalCandidate(
                chunk_id=cid,
                document_id=row.document_id,
                document_title=row.title,
                ordinal=row.ordinal,
                page_start=row.page_start,
                page_end=row.page_end,
                content=row.content,
                lexical_rank=lex_rank.get(cid),
                dense_rank=den_rank.get(cid),
                fused_rank=fused_rank.get(cid),
                rerank_rank=rerank_rank.get(cid),
                lexical_score=lex_score.get(cid),
                dense_score=den_score.get(cid),
                fused_score=fused_score.get(cid),
                rerank_score=rerank_score.get(cid),
                final_rank=index + 1,
                selected=cid in selected_ids,
            )
        )

    selected = [candidate for candidate in candidates if candidate.selected]
    return RetrievalOutcome(mode=mode, candidates=candidates, selected=selected, timings_ms=timings)
