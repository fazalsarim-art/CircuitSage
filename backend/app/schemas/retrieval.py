"""Schemas for the retrieval/search endpoint."""

import uuid

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=1000)
    mode: str = "lexical"
    top_k: int = Field(default=10, ge=1, le=50)
    document_ids: list[uuid.UUID] | None = None


class SearchHit(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    ordinal: int
    page_start: int
    page_end: int
    score: float
    preview: str


class SearchResponse(BaseModel):
    mode: str
    query: str
    hits: list[SearchHit]
    timings_ms: dict[str, float]
