"""Identity tables: users and refresh tokens (§8.3)."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import UserRole, enum_column

if TYPE_CHECKING:
    from app.db.models.conversation import Conversation
    from app.db.models.document import Document


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[UserRole] = mapped_column(
        enum_column(UserRole, "user_role"), nullable=False, server_default=text("'member'")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    daily_query_limit: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1000")
    )

    documents: Mapped[list["Document"]] = relationship(back_populates="owner")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="user")

    __table_args__ = (
        # Case-insensitive unique email.
        Index("uq_users_email_lower", text("lower(email)"), unique=True),
        CheckConstraint("daily_query_limit BETWEEN 1 AND 10000", name="daily_query_limit_range"),
    )


class RefreshToken(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    family_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)

    __table_args__ = (
        Index("uq_refresh_tokens_token_hash", "token_hash", unique=True),
        Index("ix_refresh_tokens_user_id", "user_id"),
        Index("ix_refresh_tokens_expires_at", "expires_at"),
    )
