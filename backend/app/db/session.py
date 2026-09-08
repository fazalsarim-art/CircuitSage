"""Database engine and session factory.

Uses a synchronous SQLAlchemy engine with the psycopg (v3) driver. External clients are
created here so tests and request handlers can obtain sessions through ``get_db``.
"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_settings = get_settings()

engine = create_engine(_settings.database_url, pool_pre_ping=True, future=True)

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a database session."""
    with SessionLocal() as session:
        yield session
