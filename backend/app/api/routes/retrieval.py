"""Retrieval search endpoint (§8.12). Supports lexical, dense, hybrid, reranked_hybrid."""

import time
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_embedder, get_reranker, get_vector_store
from app.core.errors import APIError
from app.db.models.document import Chunk, Document
from app.db.models.enums import DocumentStatus
from app.db.models.user import User
from app.db.session import get_db
from app.retrieval.lexical import visibility_clause
from app.retrieval.pipeline import run_retrieval
from app.retrieval.reranker import Reranker
from app.schemas.retrieval import SearchHit, SearchRequest, SearchResponse
from app.services.embeddings import Embedder
from app.services.vector_store import VectorStore

router = APIRouter(prefix="/retrieval", tags=["retrieval"])

DbDep = Annotated[Session, Depends(get_db)]
EmbedderDep = Annotated[Embedder, Depends(get_embedder)]
VectorStoreDep = Annotated[VectorStore, Depends(get_vector_store)]
RerankerDep = Annotated[Reranker, Depends(get_reranker)]

_SUPPORTED_MODES = ("lexical", "dense", "hybrid", "reranked_hybrid")
_PREVIEW_CHARS = 500


def _corpus_has_content(db: Session, user: User) -> bool:
    stmt = (
        select(Chunk.id)
        .join(Document, Document.id == Chunk.document_id)
        .where(Document.status == DocumentStatus.indexed)
    )
    clause = visibility_clause(user)
    if clause is not None:
        stmt = stmt.where(clause)
    return db.scalar(stmt.limit(1)) is not None


def _best_score(candidate) -> float:
    for value in (
        candidate.rerank_score,
        candidate.fused_score,
        candidate.dense_score,
        candidate.lexical_score,
    ):
        if value is not None:
            return value
    return 0.0


@router.post("/search", response_model=SearchResponse)
def search(
    payload: SearchRequest,
    user: CurrentUser,
    db: DbDep,
    embedder: EmbedderDep,
    vector_store: VectorStoreDep,
    reranker: RerankerDep,
) -> SearchResponse:
    if payload.mode not in _SUPPORTED_MODES:
        raise APIError(422, "invalid_mode", f"mode must be one of {_SUPPORTED_MODES}.")
    if not _corpus_has_content(db, user):
        raise APIError(400, "corpus_empty", "No indexed documents are available to search.")

    start = time.perf_counter()
    try:
        outcome = run_retrieval(
            db,
            user,
            payload.query,
            payload.mode,
            payload.top_k,
            embedder=embedder,
            vector_store=vector_store,
            reranker=reranker,
            document_ids=payload.document_ids,
        )
    except APIError:
        raise
    except Exception as exc:
        raise APIError(503, "dense_unavailable", "Retrieval is unavailable.") from exc

    hits = [
        SearchHit(
            chunk_id=c.chunk_id,
            document_id=c.document_id,
            document_title=c.document_title,
            ordinal=c.ordinal,
            page_start=c.page_start,
            page_end=c.page_end,
            score=_best_score(c),
            preview=c.content[:_PREVIEW_CHARS],
        )
        for c in outcome.selected
    ]
    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
    timings = {**outcome.timings_ms, "total": elapsed_ms}
    return SearchResponse(mode=payload.mode, query=payload.query, hits=hits, timings_ms=timings)
