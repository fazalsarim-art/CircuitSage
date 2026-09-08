"""Benchmark and evaluation tables (§8.5)."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Double,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import (
    BenchmarkStatus,
    DatasetSplit,
    Difficulty,
    EvalStatus,
    RetrievalMode,
    enum_column,
)


class BenchmarkVersion(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "benchmark_versions"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[BenchmarkStatus] = mapped_column(
        enum_column(BenchmarkStatus, "benchmark_status"),
        nullable=False,
        server_default=text("'draft'"),
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_commit: Mapped[str | None] = mapped_column(String(40), nullable=True)

    __table_args__ = (Index("uq_benchmark_versions_name_version", "name", "version", unique=True),)


class BenchmarkCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "benchmark_cases"

    benchmark_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("benchmark_versions.id", ondelete="CASCADE"), nullable=False
    )
    external_id: Mapped[str] = mapped_column(String(80), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    difficulty: Mapped[Difficulty] = mapped_column(
        enum_column(Difficulty, "difficulty"), nullable=False
    )
    split: Mapped[DatasetSplit] = mapped_column(
        enum_column(DatasetSplit, "dataset_split"), nullable=False
    )
    expected_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_feedback_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("feedback.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        Index(
            "uq_benchmark_cases_benchmark_version_id_external_id",
            "benchmark_version_id",
            "external_id",
            unique=True,
        ),
        CheckConstraint("char_length(question) BETWEEN 10 AND 1000", name="question_length"),
    )


class RelevanceJudgment(CreatedAtMixin, Base):
    __tablename__ = "relevance_judgments"

    benchmark_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("benchmark_cases.id", ondelete="CASCADE"), primary_key=True
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chunks.id", ondelete="CASCADE"), primary_key=True
    )
    relevance: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    judged_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    judged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (CheckConstraint("relevance BETWEEN 0 AND 3", name="relevance_range"),)


class EvalRun(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "eval_runs"

    benchmark_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("benchmark_versions.id", ondelete="CASCADE"), nullable=False
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[EvalStatus] = mapped_column(
        enum_column(EvalStatus, "eval_status"),
        nullable=False,
        server_default=text("'queued'"),
    )
    retrieval_mode: Mapped[RetrievalMode] = mapped_column(
        enum_column(RetrievalMode, "retrieval_mode"), nullable=False
    )
    top_k: Mapped[int] = mapped_column(Integer, nullable=False)
    candidate_k: Mapped[int] = mapped_column(Integer, nullable=False)
    rrf_k: Mapped[int] = mapped_column(Integer, nullable=False)
    reranker_model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    embedding_model: Mapped[str] = mapped_column(String(120), nullable=False)
    corpus_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index(
            "ix_eval_runs_benchmark_version_id_created_at",
            "benchmark_version_id",
            "created_at",
        ),
        CheckConstraint("top_k BETWEEN 1 AND 100", name="top_k_range"),
    )


class EvalResult(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "eval_results"

    eval_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("eval_runs.id", ondelete="CASCADE"), nullable=False
    )
    benchmark_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("benchmark_cases.id", ondelete="CASCADE"), nullable=False
    )
    ranked_chunk_ids: Mapped[list[uuid.UUID] | None] = mapped_column(ARRAY(Uuid), nullable=True)
    ranked_relevances: Mapped[list[int] | None] = mapped_column(ARRAY(SmallInteger), nullable=True)
    hit_at_5: Mapped[float | None] = mapped_column(Double, nullable=True)
    recall_at_5: Mapped[float | None] = mapped_column(Double, nullable=True)
    reciprocal_rank: Mapped[float | None] = mapped_column(Double, nullable=True)
    ndcg_at_10: Mapped[float | None] = mapped_column(Double, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    trace: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    __table_args__ = (
        Index(
            "uq_eval_results_eval_run_id_benchmark_case_id",
            "eval_run_id",
            "benchmark_case_id",
            unique=True,
        ),
        Index("ix_eval_results_eval_run_id", "eval_run_id"),
        Index("ix_eval_results_benchmark_case_id", "benchmark_case_id"),
    )
