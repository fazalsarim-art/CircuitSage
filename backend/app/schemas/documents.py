"""Request/response schemas for document and job endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentUploadResponse(BaseModel):
    document_id: uuid.UUID
    job_id: uuid.UUID
    status: str


class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    status: str
    visibility: str
    page_count: int | None
    chunk_count: int
    source_url: str | None
    publisher: str | None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    items: list[DocumentSummary]
    next_cursor: str | None


class ChunkPreview(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ordinal: int
    heading: str | None
    page_start: int
    page_end: int
    token_count: int
    preview: str


class ChunkListResponse(BaseModel):
    items: list[ChunkPreview]
    next_cursor: str | None


class JobStatusResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    status: str
    attempt: int
    max_attempts: int
    error_code: str | None
    error_detail: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class DocumentDeletedResponse(BaseModel):
    document_id: uuid.UUID
    status: str
