"""Feedback and feedback-correction tables (§8.4)."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import FeedbackReason, FeedbackStatus, enum_column


class Feedback(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "feedback"

    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    reason: Mapped[FeedbackReason | None] = mapped_column(
        enum_column(FeedbackReason, "feedback_reason"), nullable=True
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[FeedbackStatus] = mapped_column(
        enum_column(FeedbackStatus, "feedback_status"),
        nullable=False,
        server_default=text("'unresolved'"),
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("uq_feedback_user_id_message_id", "user_id", "message_id", unique=True),
        CheckConstraint("rating IN (0, 1)", name="rating_binary"),
        CheckConstraint(
            "comment IS NULL OR char_length(comment) <= 2000", name="comment_max_length"
        ),
    )


class FeedbackCorrection(CreatedAtMixin, Base):
    __tablename__ = "feedback_corrections"

    feedback_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feedback.id", ondelete="CASCADE"), primary_key=True
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chunks.id", ondelete="CASCADE"), primary_key=True
    )
    relevance: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    __table_args__ = (CheckConstraint("relevance BETWEEN 1 AND 3", name="relevance_range"),)


class FeedbackEvent(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Append-only audit trail of feedback lifecycle actions (submitted, reviewed, promoted)."""

    __tablename__ = "feedback_events"

    feedback_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feedback.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_feedback_events_feedback_id_created_at", "feedback_id", "created_at"),
    )
