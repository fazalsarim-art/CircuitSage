"""Document, ingestion job, and chunk tables (§8.3)."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import (
    DocumentStatus,
    JobStatus,
    Visibility,
    enum_column,
)

if TYPE_CHECKING:
    from app.db.models.user import User


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(160), nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        enum_column(DocumentStatus, "document_status"),
        nullable=False,
        server_default=text("'uploaded'"),
    )
    visibility: Mapped[Visibility] = mapped_column(
        enum_column(Visibility, "visibility"),
        nullable=False,
        server_default=text("'private'"),
    )
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    parser_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    chunker_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    embedding_dimensions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    doc_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    owner: Mapped["User"] = relationship(back_populates="documents")
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    jobs: Mapped[list["IngestionJob"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("uq_documents_owner_id_sha256", "owner_id", "sha256", unique=True),
        Index("ix_documents_owner_id", "owner_id"),
        Index("ix_documents_status", "status"),
        Index("ix_documents_visibility", "visibility"),
        CheckConstraint(
            "page_count IS NULL OR page_count BETWEEN 1 AND 300", name="page_count_range"
        ),
    )


class IngestionJob(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "ingestion_jobs"

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[JobStatus] = mapped_column(
        enum_column(JobStatus, "job_status"),
        nullable=False,
        server_default=text("'queued'"),
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("3"))
    locked_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    document: Mapped["Document"] = relationship(back_populates="jobs")

    __table_args__ = (
        Index("ix_ingestion_jobs_status_created_at", "status", "created_at"),
        # At most one active (queued/processing) job per document.
        Index(
            "uq_ingestion_jobs_active_document",
            "document_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'processing')"),
        ),
    )


class Chunk(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    heading: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', coalesce(heading, '') || ' ' || content)",
            persisted=True,
        ),
        nullable=True,
    )
    chunk_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    document: Mapped["Document"] = relationship(back_populates="chunks")

    __table_args__ = (
        Index("uq_chunks_document_id_ordinal", "document_id", "ordinal", unique=True),
        Index("uq_chunks_document_id_checksum", "document_id", "checksum", unique=True),
        Index("ix_chunks_document_id", "document_id"),
        Index("ix_chunks_search_vector", "search_vector", postgresql_using="gin"),
        CheckConstraint("page_start >= 1", name="page_start_min"),
        CheckConstraint("page_end >= page_start", name="page_end_after_start"),
    )
