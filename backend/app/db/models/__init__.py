"""Import all models so ``Base.metadata`` is fully populated (used by Alembic)."""

from app.db.base import Base
from app.db.models.benchmark import (
    BenchmarkCase,
    BenchmarkVersion,
    EvalResult,
    EvalRun,
    RelevanceJudgment,
)
from app.db.models.conversation import Conversation, Message, RetrievalResult
from app.db.models.document import Chunk, Document, DocumentSource, IngestionJob
from app.db.models.feedback import Feedback, FeedbackCorrection
from app.db.models.user import RefreshToken, User

__all__ = [
    "Base",
    "User",
    "RefreshToken",
    "Document",
    "DocumentSource",
    "IngestionJob",
    "Chunk",
    "Conversation",
    "Message",
    "RetrievalResult",
    "Feedback",
    "FeedbackCorrection",
    "BenchmarkVersion",
    "BenchmarkCase",
    "RelevanceJudgment",
    "EvalRun",
    "EvalResult",
]
