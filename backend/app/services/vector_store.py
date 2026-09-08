"""Qdrant vector store wrapper.

Qdrant is a derived index: every point uses the chunk UUID as its id and stores only a
small payload (document_id, owner_id, visibility, page range) for filtering. Chunk text
is never duplicated here — results are hydrated from PostgreSQL.
"""

import uuid
from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.core.config import Settings


@dataclass(frozen=True)
class VectorHit:
    chunk_id: uuid.UUID
    score: float


class CollectionDimensionMismatch(RuntimeError):
    """Raised when an existing collection's vector size differs from the expected size."""


class VectorStore:
    def __init__(self, client: QdrantClient, collection: str) -> None:
        self._client = client
        self.collection = collection

    def ensure_collection(self, dimensions: int) -> None:
        if self._client.collection_exists(self.collection):
            info = self._client.get_collection(self.collection)
            existing = info.config.params.vectors.size
            if existing != dimensions:
                raise CollectionDimensionMismatch(
                    f"Collection '{self.collection}' has dimension {existing}, "
                    f"but {dimensions} was requested. Use a new versioned collection."
                )
            return
        self._client.create_collection(
            collection_name=self.collection,
            vectors_config=qmodels.VectorParams(size=dimensions, distance=qmodels.Distance.COSINE),
        )

    def recreate_collection(self, dimensions: int) -> None:
        try:
            self._client.delete_collection(self.collection)
        except Exception:
            pass
        self.ensure_collection(dimensions)

    def upsert_chunks(self, points: list[tuple[uuid.UUID, list[float], dict]]) -> None:
        if not points:
            return
        self._client.upsert(
            collection_name=self.collection,
            points=[
                qmodels.PointStruct(id=str(chunk_id), vector=vector, payload=payload)
                for chunk_id, vector, payload in points
            ],
        )

    def delete_by_document(self, document_id: uuid.UUID) -> None:
        try:
            self._client.delete(
                collection_name=self.collection,
                points_selector=qmodels.FilterSelector(
                    filter=qmodels.Filter(
                        must=[
                            qmodels.FieldCondition(
                                key="document_id",
                                match=qmodels.MatchValue(value=str(document_id)),
                            )
                        ]
                    )
                ),
            )
        except Exception:
            # Collection may not exist yet (document never embedded) — nothing to delete.
            pass

    def search(
        self, vector: list[float], top_k: int, query_filter: qmodels.Filter | None = None
    ) -> list[VectorHit]:
        response = self._client.query_points(
            collection_name=self.collection,
            query=vector,
            limit=top_k,
            query_filter=query_filter,
            with_payload=False,
        )
        return [
            VectorHit(uuid.UUID(str(point.id)), float(point.score)) for point in response.points
        ]


def build_vector_store(settings: Settings, collection: str | None = None) -> VectorStore:
    client = QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
        timeout=5.0,
    )
    return VectorStore(client, collection or settings.qdrant_collection)
