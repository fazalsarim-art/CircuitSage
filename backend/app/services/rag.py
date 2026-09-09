"""Chat orchestration: retrieve evidence, generate a grounded answer, and persist the
conversation turn (user + assistant messages) with the full retrieval trace.
"""

import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import APIError
from app.db.models.conversation import Conversation, Message, RetrievalResult
from app.db.models.enums import MessageRole
from app.db.models.user import User
from app.retrieval.pipeline import RetrievalCandidate, run_retrieval
from app.services.answers import Evidence, generate_answer

_RERANK_MODE = "reranked_hybrid"


def queries_used_today(db: Session, user: User) -> int:
    """Number of questions the user has asked since 00:00 UTC today."""
    day_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        db.scalar(
            select(func.count(Message.id))
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(
                Conversation.user_id == user.id,
                Message.role == MessageRole.user,
                Message.created_at >= day_start,
            )
        )
        or 0
    )


def assert_within_daily_limit(db: Session, user: User) -> None:
    """Raise 429 when the user has reached their per-day question quota (§7.12)."""
    if queries_used_today(db, user) >= user.daily_query_limit:
        raise APIError(
            429,
            "daily_limit_exceeded",
            "Daily query limit reached. Please try again tomorrow.",
        )


@dataclass
class ChatTurn:
    user_message: Message
    assistant_message: Message
    answer_status: str
    sources: list[dict]
    timings_ms: dict[str, float]


def _effective_mode(mode: str, reranker_enabled: bool | None) -> str:
    if reranker_enabled is True and mode == "hybrid":
        return _RERANK_MODE
    if reranker_enabled is False and mode == _RERANK_MODE:
        return "hybrid"
    return mode


def _source(label: str, candidate: RetrievalCandidate) -> dict:
    return {
        "label": label,
        "chunk_id": candidate.chunk_id,
        "document_id": candidate.document_id,
        "document_title": candidate.document_title,
        "page_start": candidate.page_start,
        "page_end": candidate.page_end,
        "preview": candidate.content[:500],
    }


def answer_question(
    db: Session,
    *,
    settings: Settings,
    user: User,
    conversation: Conversation,
    content: str,
    mode: str,
    top_k: int,
    reranker_enabled: bool | None,
    document_ids: list[uuid.UUID] | None,
    embedder,
    vector_store,
    reranker,
    answer_client,
    request_id: uuid.UUID,
) -> ChatTurn:
    effective_mode = _effective_mode(mode, reranker_enabled)

    start = time.perf_counter()
    try:
        outcome = run_retrieval(
            db,
            user,
            content,
            effective_mode,
            top_k,
            embedder=embedder,
            vector_store=vector_store,
            reranker=reranker,
            document_ids=document_ids,
        )
    except Exception as exc:
        raise APIError(503, "retrieval_unavailable", "Retrieval is currently unavailable.") from exc

    evidence = [
        Evidence(label=f"C{i + 1}", chunk_id=c.chunk_id, content=c.content)
        for i, c in enumerate(outcome.selected)
    ]
    gen_start = time.perf_counter()
    answer = generate_answer(answer_client, settings, content, evidence)
    generation_ms = round((time.perf_counter() - gen_start) * 1000, 2)
    total_ms = round((time.perf_counter() - start) * 1000, 2)

    user_message = Message(
        conversation_id=conversation.id,
        role=MessageRole.user,
        content=content,
        request_id=request_id,
    )
    db.add(user_message)
    db.flush()

    assistant_message = Message(
        conversation_id=conversation.id,
        role=MessageRole.assistant,
        content=answer.text,
        retrieval_mode=effective_mode,
        model_name=settings.openai_chat_model,
        prompt_version="grounded-v1",
        request_id=request_id,
        latency_ms=int(total_ms),
        input_tokens=answer.input_tokens,
        output_tokens=answer.output_tokens,
        answer_status=answer.status,
    )
    db.add(assistant_message)
    db.flush()

    for candidate in outcome.candidates:
        db.add(
            RetrievalResult(
                message_id=assistant_message.id,
                chunk_id=candidate.chunk_id,
                retrieval_mode=effective_mode,
                lexical_rank=candidate.lexical_rank,
                dense_rank=candidate.dense_rank,
                fused_rank=candidate.fused_rank,
                rerank_rank=candidate.rerank_rank,
                lexical_score=candidate.lexical_score,
                dense_score=candidate.dense_score,
                fused_score=candidate.fused_score,
                rerank_score=candidate.rerank_score,
                selected_for_context=candidate.selected,
                timings=outcome.timings_ms,
            )
        )

    conversation.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(user_message)
    db.refresh(assistant_message)

    cited = set(answer.cited_labels)
    if answer.status.value == "answered":
        sources = [
            _source(f"C{i + 1}", c) for i, c in enumerate(outcome.selected) if (i + 1) in cited
        ]
    else:
        # For insufficient/failed answers, still surface the closest passages.
        sources = [_source(f"C{i + 1}", c) for i, c in enumerate(outcome.selected)]

    timings = {**outcome.timings_ms, "generation": generation_ms, "total": total_ms}
    return ChatTurn(
        user_message=user_message,
        assistant_message=assistant_message,
        answer_status=answer.status.value,
        sources=sources,
        timings_ms=timings,
    )
