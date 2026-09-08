"""Schemas for conversations, messages, sources, and the retrieval trace."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=160)


class ConversationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(BaseModel):
    items: list[ConversationSummary]
    next_cursor: str | None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    answer_status: str | None
    retrieval_mode: str | None
    created_at: datetime


class ConversationDetail(BaseModel):
    id: uuid.UUID
    title: str
    messages: list[MessageOut]


class MessageCreate(BaseModel):
    content: str = Field(min_length=3, max_length=1000)
    retrieval_mode: str = "hybrid"
    top_k: int = Field(default=8, ge=1, le=20)
    reranker_enabled: bool | None = None
    document_ids: list[uuid.UUID] | None = None


class Source(BaseModel):
    label: str
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    page_start: int
    page_end: int
    preview: str


class ChatResponse(BaseModel):
    user_message: MessageOut
    assistant_message: MessageOut
    answer_status: str
    sources: list[Source]
    timings_ms: dict[str, float]


class RetrievalResultOut(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    page_start: int
    page_end: int
    lexical_rank: int | None
    dense_rank: int | None
    fused_rank: int | None
    rerank_rank: int | None
    lexical_score: float | None
    dense_score: float | None
    fused_score: float | None
    rerank_score: float | None
    selected_for_context: bool


class RetrievalTraceResponse(BaseModel):
    message_id: uuid.UUID
    retrieval_mode: str | None
    results: list[RetrievalResultOut]
