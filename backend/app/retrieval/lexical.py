"""Lexical retrieval over PostgreSQL full-text search (websearch_to_tsquery + ts_rank_cd)."""

import uuid

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.db.models.document import Chunk, Document
from app.db.models.enums import DocumentStatus, UserRole, Visibility
from app.db.models.user import User
from app.schemas.retrieval import SearchHit

_PREVIEW_CHARS = 500


def visibility_clause(user: User) -> ColumnElement[bool] | None:
    """Restrict to the user's own documents plus shared ones (admins see everything)."""
    if user.role == UserRole.admin:
        return None
    return (Document.owner_id == user.id) | (Document.visibility == Visibility.shared)


def lexical_search(
    db: Session,
    user: User,
    query: str,
    top_k: int,
    document_ids: list[uuid.UUID] | None = None,
) -> list[SearchHit]:
    tsquery = func.websearch_to_tsquery("english", query)
    score = func.ts_rank_cd(Chunk.search_vector, tsquery).label("score")
    stmt = (
        select(
            Chunk.id,
            Chunk.document_id,
            Document.title,
            Chunk.ordinal,
            Chunk.page_start,
            Chunk.page_end,
            Chunk.content,
            score,
        )
        .join(Document, Document.id == Chunk.document_id)
        .where(
            Chunk.search_vector.op("@@")(tsquery),
            Document.status == DocumentStatus.indexed,
        )
    )
    clause = visibility_clause(user)
    if clause is not None:
        stmt = stmt.where(clause)
    if document_ids:
        stmt = stmt.where(Chunk.document_id.in_(document_ids))
    stmt = stmt.order_by(score.desc(), Chunk.id).limit(top_k)

    return [
        SearchHit(
            chunk_id=row.id,
            document_id=row.document_id,
            document_title=row.title,
            ordinal=row.ordinal,
            page_start=row.page_start,
            page_end=row.page_end,
            score=float(row.score),
            preview=row.content[:_PREVIEW_CHARS],
        )
        for row in db.execute(stmt).all()
    ]
