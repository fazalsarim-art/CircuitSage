"""Dense retrieval: embed the query, search Qdrant with visibility filters, hydrate from PG."""

import uuid

from qdrant_client.http import models as qmodels
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.document import Chunk, Document
from app.db.models.enums import DocumentStatus, UserRole, Visibility
from app.db.models.user import User
from app.schemas.retrieval import SearchHit
from app.services.embeddings import Embedder
from app.services.vector_store import VectorStore

_PREVIEW_CHARS = 500


def _qdrant_filter(user: User, document_ids: list[uuid.UUID] | None) -> qmodels.Filter | None:
    conditions: list = []
    if user.role != UserRole.admin:
        conditions.append(
            qmodels.Filter(
                should=[
                    qmodels.FieldCondition(
                        key="owner_id", match=qmodels.MatchValue(value=str(user.id))
                    ),
                    qmodels.FieldCondition(
                        key="visibility", match=qmodels.MatchValue(value="shared")
                    ),
                ]
            )
        )
    if document_ids:
        conditions.append(
            qmodels.FieldCondition(
                key="document_id",
                match=qmodels.MatchAny(any=[str(d) for d in document_ids]),
            )
        )
    return qmodels.Filter(must=conditions) if conditions else None


def dense_search(
    db: Session,
    vector_store: VectorStore,
    embedder: Embedder,
    user: User,
    query: str,
    top_k: int,
    document_ids: list[uuid.UUID] | None = None,
) -> list[SearchHit]:
    vector = embedder.embed([query])[0]
    hits = vector_store.search(vector, top_k, _qdrant_filter(user, document_ids))
    if not hits:
        return []

    score_by_id = {hit.chunk_id: hit.score for hit in hits}
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
        .where(Chunk.id.in_(list(score_by_id)), Document.status == DocumentStatus.indexed)
    )
    if user.role != UserRole.admin:
        stmt = stmt.where(
            (Document.owner_id == user.id) | (Document.visibility == Visibility.shared)
        )
    rows = {row.id: row for row in db.execute(stmt).all()}

    results: list[SearchHit] = []
    for chunk_id, score in sorted(score_by_id.items(), key=lambda kv: kv[1], reverse=True):
        row = rows.get(chunk_id)
        if row is None:
            continue
        results.append(
            SearchHit(
                chunk_id=row.id,
                document_id=row.document_id,
                document_title=row.title,
                ordinal=row.ordinal,
                page_start=row.page_start,
                page_end=row.page_end,
                score=score,
                preview=row.content[:_PREVIEW_CHARS],
            )
        )
    return results
