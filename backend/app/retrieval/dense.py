"""Dense retrieval: embed the query and search Qdrant with visibility filters.

Returns chunk ids + scores only; full chunk content is hydrated from PostgreSQL by the
retrieval pipeline (Qdrant stores no chunk text).
"""

import uuid

from qdrant_client.http import models as qmodels

from app.db.models.enums import UserRole
from app.db.models.user import User
from app.services.embeddings import Embedder
from app.services.vector_store import VectorStore


def dense_qdrant_filter(user: User, document_ids: list[uuid.UUID] | None) -> qmodels.Filter | None:
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


def dense_search_ids(
    vector_store: VectorStore,
    embedder: Embedder,
    user: User,
    query: str,
    limit: int,
    document_ids: list[uuid.UUID] | None = None,
) -> list[tuple[uuid.UUID, float]]:
    vector = embedder.embed([query])[0]
    hits = vector_store.search(vector, limit, dense_qdrant_filter(user, document_ids))
    return [(hit.chunk_id, hit.score) for hit in hits]
