"""Schemas for benchmark authoring and JSONL import/export."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class JudgmentIn(BaseModel):
    chunk_id: uuid.UUID
    relevance: int = Field(ge=0, le=3)
    rationale: str | None = None


class BenchmarkCaseIn(BaseModel):
    """A benchmark case, also used as the JSONL line schema (schema version 1)."""

    external_id: str = Field(min_length=1, max_length=80)
    question: str = Field(min_length=10, max_length=1000)
    category: str = Field(min_length=1, max_length=80)
    difficulty: str
    split: str
    expected_answer: str | None = None
    notes: str | None = None
    judgments: list[JudgmentIn] = Field(default_factory=list)


class BenchmarkCaseUpdate(BaseModel):
    question: str | None = Field(default=None, min_length=10, max_length=1000)
    category: str | None = Field(default=None, min_length=1, max_length=80)
    difficulty: str | None = None
    split: str | None = None
    expected_answer: str | None = None
    notes: str | None = None
    judgments: list[JudgmentIn] | None = None


class JudgmentOut(BaseModel):
    chunk_id: uuid.UUID
    relevance: int
    rationale: str | None


class CaseOut(BaseModel):
    id: uuid.UUID
    external_id: str
    question: str
    category: str
    difficulty: str
    split: str
    expected_answer: str | None
    notes: str | None
    judgments: list[JudgmentOut]


class CaseListResponse(BaseModel):
    items: list[CaseOut]


class VersionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None


class VersionOut(BaseModel):
    id: uuid.UUID
    name: str
    version: int
    status: str
    description: str | None
    published_at: datetime | None
    source_commit: str | None
    created_at: datetime
    case_count: int


class VersionListResponse(BaseModel):
    items: list[VersionOut]


class PublishRequest(BaseModel):
    confirmation: str
    source_commit: str | None = None


class ImportResult(BaseModel):
    imported: int
    judgments: int
