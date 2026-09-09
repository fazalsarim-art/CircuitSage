"""Schemas for structured feedback, admin review, corrected evidence, and audit history."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CorrectionIn(BaseModel):
    """A corrected relevance judgment supplied during admin review."""

    chunk_id: uuid.UUID
    relevance: int = Field(ge=1, le=3)


class CorrectionOut(BaseModel):
    chunk_id: uuid.UUID
    relevance: int
    document_title: str | None = None
    page_start: int | None = None
    page_end: int | None = None


class FeedbackSubmit(BaseModel):
    """A user's structured feedback on an assistant answer (upserted per message)."""

    rating: int = Field(ge=0, le=1)
    reason: str | None = None
    comment: str | None = Field(default=None, max_length=2000)


class DraftCaseSpec(BaseModel):
    """Where and how to file a draft benchmark case when promoting reviewed feedback."""

    benchmark_version_id: uuid.UUID
    external_id: str = Field(min_length=1, max_length=80)
    category: str = Field(min_length=1, max_length=80)
    difficulty: str = "medium"
    split: str = "test"


class FeedbackReviewRequest(BaseModel):
    """An admin's review decision. Corrections and draft promotion are explicit, never automatic."""

    status: str  # resolved | ignored | promoted_to_draft
    resolution_note: str | None = Field(default=None, max_length=2000)
    corrections: list[CorrectionIn] | None = None
    draft: DraftCaseSpec | None = None


class FeedbackEventOut(BaseModel):
    id: uuid.UUID
    action: str
    actor_id: uuid.UUID | None
    note: str | None
    created_at: datetime


class FeedbackOut(BaseModel):
    id: uuid.UUID
    message_id: uuid.UUID
    user_id: uuid.UUID
    rating: int
    reason: str | None
    comment: str | None
    status: str
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    resolution_note: str | None
    created_at: datetime
    updated_at: datetime
    question: str | None
    answer: str | None
    answer_status: str | None
    retrieval_mode: str | None
    corrections: list[CorrectionOut]


class FeedbackDetail(FeedbackOut):
    events: list[FeedbackEventOut]


class FeedbackListResponse(BaseModel):
    items: list[FeedbackOut]
