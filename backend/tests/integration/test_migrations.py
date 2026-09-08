"""Integration test: the initial migration applies, round-trips, and builds the expected
schema against the local Docker PostgreSQL instance.

These tests require ``docker compose up -d`` (PostgreSQL reachable at DATABASE_URL). They
downgrade to base and back to head, so run them ONLY against a disposable local database.
"""

import psycopg
import pytest
from alembic.config import Config

from alembic import command
from app.core.config import BACKEND_DIR, get_settings

EXPECTED_TABLES = {
    "users",
    "refresh_tokens",
    "documents",
    "ingestion_jobs",
    "chunks",
    "retrieval_results",
    "conversations",
    "messages",
    "feedback",
    "feedback_corrections",
    "benchmark_versions",
    "benchmark_cases",
    "relevance_judgments",
    "eval_runs",
    "eval_results",
}


@pytest.fixture(scope="module")
def alembic_config() -> Config:
    return Config(str(BACKEND_DIR / "alembic.ini"))


def _connect(autocommit: bool = False) -> psycopg.Connection:
    return psycopg.connect(get_settings().psycopg_dsn, connect_timeout=5, autocommit=autocommit)


def test_migration_round_trip_builds_schema(alembic_config: Config) -> None:
    # Full disposable-DB round trip: base -> head.
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")

    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )
        tables = {row[0] for row in cur.fetchall()}
        assert EXPECTED_TABLES.issubset(tables), EXPECTED_TABLES - tables

        # chunks.search_vector must be a STORED generated column.
        cur.execute(
            "SELECT is_generated FROM information_schema.columns "
            "WHERE table_name = 'chunks' AND column_name = 'search_vector'"
        )
        assert cur.fetchone()[0] == "ALWAYS"

        # It must be backed by a GIN index.
        cur.execute(
            "SELECT am.amname FROM pg_index i "
            "JOIN pg_class ic ON ic.oid = i.indexrelid "
            "JOIN pg_am am ON am.oid = ic.relam "
            "WHERE ic.relname = 'ix_chunks_search_vector'"
        )
        assert cur.fetchone()[0] == "gin"


def test_role_check_constraint_rejects_invalid_enum() -> None:
    with _connect(autocommit=True) as conn, conn.cursor() as cur, pytest.raises(psycopg.Error):
        cur.execute(
            "INSERT INTO users (email, password_hash, role) "
            "VALUES ('bad-role@example.com', 'h', 'superuser')"
        )


def test_daily_query_limit_check_constraint_rejects_out_of_range() -> None:
    with _connect(autocommit=True) as conn, conn.cursor() as cur, pytest.raises(psycopg.Error):
        cur.execute(
            "INSERT INTO users (email, password_hash, daily_query_limit) "
            "VALUES ('bad-limit@example.com', 'h', 0)"
        )
