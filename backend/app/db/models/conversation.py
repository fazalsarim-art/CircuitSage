"""Conversation, message, and retrieval-result tables (§8.4, §8.3)."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Double,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import (
    AnswerStatus,
    MessageRole,
    RetrievalMode,
    enum_column,
)

if TYPE_CHECKING:
    from app.db.models.user import User


class Conversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)

    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_conversations_user_id_updated_at", "user_id", "updated_at"),)


class Message(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[MessageRole] = mapped_column(
        enum_column(MessageRole, "message_role"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    retrieval_mode: Mapped[RetrievalMode | None] = mapped_column(
        enum_column(RetrievalMode, "retrieval_mode"), nullable=True
    )
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    request_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    answer_status: Mapped[AnswerStatus | None] = mapped_column(
        enum_column(AnswerStatus, "answer_status"), nullable=True
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    retrieval_results: Mapped[list["RetrievalResult"]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_messages_conversation_id_created_at", "conversation_id", "created_at"),
    )


class RetrievalResult(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "retrieval_results"

    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False
    )
    retrieval_mode: Mapped[RetrievalMode] = mapped_column(
        enum_column(RetrievalMode, "retrieval_mode"), nullable=False
    )
    lexical_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dense_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fused_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rerank_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lexical_score: Mapped[float | None] = mapped_column(Double, nullable=True)
    dense_score: Mapped[float | None] = mapped_column(Double, nullable=True)
    fused_score: Mapped[float | None] = mapped_column(Double, nullable=True)
    rerank_score: Mapped[float | None] = mapped_column(Double, nullable=True)
    selected_for_context: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    timings: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    message: Mapped["Message"] = relationship(back_populates="retrieval_results")

    __table_args__ = (
        Index(
            "uq_retrieval_results_message_id_chunk_id",
            "message_id",
            "chunk_id",
            unique=True,
        ),
        Index("ix_retrieval_results_message_id", "message_id"),
        Index("ix_retrieval_results_chunk_id", "chunk_id"),
    )
