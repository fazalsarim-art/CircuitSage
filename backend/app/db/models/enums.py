"""Enumerated values (§8.6).

Stored as ``VARCHAR`` columns with named ``CHECK`` constraints (via ``native_enum=False``)
rather than native PostgreSQL ENUM types — this keeps migrations simple (a new value is a
check-constraint change, not an ``ALTER TYPE``) while preserving Python-side type safety.
"""

import enum

from sqlalchemy import Enum as SAEnum


class UserRole(enum.StrEnum):
    admin = "admin"
    member = "member"


class DocumentStatus(enum.StrEnum):
    uploaded = "uploaded"
    queued = "queued"
    processing = "processing"
    indexed = "indexed"
    failed = "failed"
    deleting = "deleting"


class JobStatus(enum.StrEnum):
    queued = "queued"
    processing = "processing"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class Visibility(enum.StrEnum):
    private = "private"
    shared = "shared"


class RetrievalMode(enum.StrEnum):
    lexical = "lexical"
    dense = "dense"
    hybrid = "hybrid"
    reranked_hybrid = "reranked_hybrid"


class MessageRole(enum.StrEnum):
    user = "user"
    assistant = "assistant"


class AnswerStatus(enum.StrEnum):
    answered = "answered"
    insufficient_evidence = "insufficient_evidence"
    generation_failed = "generation_failed"


class FeedbackReason(enum.StrEnum):
    helpful = "helpful"
    retrieval_miss = "retrieval_miss"
    ranking_error = "ranking_error"
    chunking_error = "chunking_error"
    unsupported_answer = "unsupported_answer"
    citation_error = "citation_error"
    source_gap = "source_gap"
    user_expectation = "user_expectation"
    other = "other"


class FeedbackStatus(enum.StrEnum):
    unresolved = "unresolved"
    resolved = "resolved"
    ignored = "ignored"
    promoted_to_draft = "promoted_to_draft"


class BenchmarkStatus(enum.StrEnum):
    draft = "draft"
    published = "published"
    archived = "archived"


class Difficulty(enum.StrEnum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class DatasetSplit(enum.StrEnum):
    train = "train"
    validation = "validation"
    test = "test"


class EvalStatus(enum.StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


def enum_column(py_enum: type[enum.Enum], name: str) -> SAEnum:
    """A VARCHAR + named CHECK constraint for the given Python enum."""
    return SAEnum(
        py_enum,
        name=name,
        native_enum=False,
        values_callable=lambda e: [member.value for member in e],
    )
