"""Retrieval search endpoint (§8.12). Phase 5 supports lexical and dense modes."""

import time
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_embedder, get_vector_store
from app.core.errors import APIError
from app.db.models.document import Chunk, Document
from app.db.models.enums import DocumentStatus
from app.db.models.user import User
from app.db.session import get_db
from app.retrieval.dense import dense_search
from app.retrieval.lexical import lexical_search, visibility_clause
from app.schemas.retrieval import SearchRequest, SearchResponse
from app.services.embeddings import Embedder
from app.services.vector_store import VectorStore

router = APIRouter(prefix="/retrieval", tags=["retrieval"])

DbDep = Annotated[Session, Depends(get_db)]
EmbedderDep = Annotated[Embedder, Depends(get_embedder)]
VectorStoreDep = Annotated[VectorStore, Depends(get_vector_store)]

_SUPPORTED_MODES = ("lexical", "dense")


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


@router.post("/search", response_model=SearchResponse)
def search(
    payload: SearchRequest,
    user: CurrentUser,
    db: DbDep,
    embedder: EmbedderDep,
    vector_store: VectorStoreDep,
) -> SearchResponse:
    if payload.mode not in _SUPPORTED_MODES:
        raise APIError(422, "invalid_mode", "mode must be 'lexical' or 'dense'.")
    if not _corpus_has_content(db, user):
        raise APIError(400, "corpus_empty", "No indexed documents are available to search.")

    start = time.perf_counter()
    if payload.mode == "lexical":
        hits = lexical_search(db, user, payload.query, payload.top_k, payload.document_ids)
    else:
        try:
            hits = dense_search(
                db, vector_store, embedder, user, payload.query, payload.top_k, payload.document_ids
            )
        except APIError:
            raise
        except Exception as exc:
            raise APIError(503, "dense_unavailable", "Dense retrieval is unavailable.") from exc

    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
    return SearchResponse(
        mode=payload.mode, query=payload.query, hits=hits, timings_ms={"total": elapsed_ms}
    )
