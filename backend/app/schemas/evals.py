"""Schemas for evaluation runs and comparisons."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class EvalRunCreate(BaseModel):
    benchmark_version_id: uuid.UUID
    retrieval_mode: str = "hybrid"
    top_k: int = Field(default=10, ge=1, le=100)
    candidate_k: int = Field(default=30, ge=1, le=200)
    rrf_k: int = Field(default=60, ge=1)
    reranker_enabled: bool = False


class EvalRunOut(BaseModel):
    id: uuid.UUID
    benchmark_version_id: uuid.UUID
    status: str
    retrieval_mode: str
    top_k: int
    candidate_k: int
    rrf_k: int
    reranker_model: str | None
    embedding_model: str
    corpus_fingerprint: str
    metrics: dict | None
    error_code: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class EvalRunListResponse(BaseModel):
    items: list[EvalRunOut]


class EvalCaseResultOut(BaseModel):
    benchmark_case_id: uuid.UUID
    hit_at_5: float | None
    recall_at_5: float | None
    reciprocal_rank: float | None
    ndcg_at_10: float | None
    latency_ms: int | None
    error_code: str | None


class EvalRunDetail(BaseModel):
    run: EvalRunOut
    results: list[EvalCaseResultOut]


class CompareResponse(BaseModel):
    left: EvalRunOut
    right: EvalRunOut
    equivalent: bool
    metric_deltas: dict[str, float]
