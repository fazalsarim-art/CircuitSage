"""Lexical retrieval over PostgreSQL full-text search (websearch_to_tsquery + ts_rank_cd)."""

import uuid

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.db.models.document import Chunk, Document
from app.db.models.enums import DocumentStatus, UserRole, Visibility
from app.db.models.user import User


def visibility_clause(user: User) -> ColumnElement[bool] | None:
    """Restrict to the user's own documents plus shared ones (admins see everything)."""
    if user.role == UserRole.admin:
        return None
    return (Document.owner_id == user.id) | (Document.visibility == Visibility.shared)


def lexical_search_ids(
    db: Session,
    user: User,
    query: str,
    limit: int,
    document_ids: list[uuid.UUID] | None = None,
) -> list[tuple[uuid.UUID, float]]:
    """Return ``(chunk_id, ts_rank_cd score)`` ordered best-first."""
    tsquery = func.websearch_to_tsquery("english", query)
    score = func.ts_rank_cd(Chunk.search_vector, tsquery)
    stmt = (
        select(Chunk.id, score)
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
    stmt = stmt.order_by(score.desc(), Chunk.id).limit(limit)
    return [(row[0], float(row[1])) for row in db.execute(stmt).all()]
