"""Conversation, message, and retrieval-trace endpoints (§8.12)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import (
    CurrentUser,
    get_answer_client,
    get_embedder,
    get_reranker,
    get_vector_store,
)
from app.core.config import Settings, get_settings
from app.core.errors import APIError
from app.db.models.conversation import Conversation, Message, RetrievalResult
from app.db.models.document import Chunk, Document
from app.db.models.enums import DocumentStatus, UserRole
from app.db.models.user import User
from app.db.session import get_db
from app.retrieval.lexical import visibility_clause
from app.schemas.chat import (
    ChatResponse,
    ConversationCreate,
    ConversationDetail,
    ConversationListResponse,
    ConversationSummary,
    MessageCreate,
    MessageOut,
    RetrievalResultOut,
    RetrievalTraceResponse,
    Source,
)
from app.services import rag

router = APIRouter(prefix="/conversations", tags=["chat"])
messages_router = APIRouter(prefix="/messages", tags=["chat"])

DbDep = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def _owned_conversation(db: Session, user: User, conversation_id: uuid.UUID) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user.id:
        raise APIError(404, "not_found", "Conversation not found.")
    return conversation


def _corpus_ready(db: Session, user: User) -> bool:
    stmt = (
        select(Chunk.id)
        .join(Document, Document.id == Chunk.document_id)
        .where(Document.status == DocumentStatus.indexed)
    )
    clause = visibility_clause(user)
    if clause is not None:
        stmt = stmt.where(clause)
    return db.scalar(stmt.limit(1)) is not None


@router.post("", status_code=201, response_model=ConversationSummary)
def create_conversation(
    payload: ConversationCreate, user: CurrentUser, db: DbDep
) -> ConversationSummary:
    conversation = Conversation(user_id=user.id, title=(payload.title or "New conversation"))
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return ConversationSummary.model_validate(conversation)


@router.get("", response_model=ConversationListResponse)
def list_conversations(
    user: CurrentUser,
    db: DbDep,
    limit: int = 20,
) -> ConversationListResponse:
    limit = max(1, min(limit, 100))
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
        .limit(limit)
    )
    items = [ConversationSummary.model_validate(row) for row in db.scalars(stmt)]
    return ConversationListResponse(items=items, next_cursor=None)


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: uuid.UUID, user: CurrentUser, db: DbDep
) -> ConversationDetail:
    conversation = _owned_conversation(db, user, conversation_id)
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at, Message.id)
    )
    messages = [MessageOut.model_validate(row) for row in db.scalars(stmt)]
    return ConversationDetail(id=conversation.id, title=conversation.title, messages=messages)


@router.post("/{conversation_id}/messages", status_code=201, response_model=ChatResponse)
def create_message(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    user: CurrentUser,
    db: DbDep,
    settings: SettingsDep,
    embedder: Annotated[object, Depends(get_embedder)],
    vector_store: Annotated[object, Depends(get_vector_store)],
    reranker: Annotated[object, Depends(get_reranker)],
    answer_client: Annotated[object, Depends(get_answer_client)],
) -> ChatResponse:
    conversation = _owned_conversation(db, user, conversation_id)
    if payload.retrieval_mode not in ("lexical", "dense", "hybrid", "reranked_hybrid"):
        raise APIError(422, "invalid_mode", "Unknown retrieval mode.")
    rag.assert_within_daily_limit(db, user)  # per-user query quota (§7.12)
    if not _corpus_ready(db, user):
        raise APIError(409, "corpus_not_ready", "No indexed documents are available.")

    turn = rag.answer_question(
        db,
        settings=settings,
        user=user,
        conversation=conversation,
        content=payload.content,
        mode=payload.retrieval_mode,
        top_k=payload.top_k,
        reranker_enabled=payload.reranker_enabled,
        document_ids=payload.document_ids,
        embedder=embedder,
        vector_store=vector_store,
        reranker=reranker,
        answer_client=answer_client,
        request_id=uuid.uuid4(),
    )
    return ChatResponse(
        user_message=MessageOut.model_validate(turn.user_message),
        assistant_message=MessageOut.model_validate(turn.assistant_message),
        answer_status=turn.answer_status,
        sources=[Source(**src) for src in turn.sources],
        timings_ms=turn.timings_ms,
    )


@messages_router.get("/{message_id}/retrieval", response_model=RetrievalTraceResponse)
def get_retrieval_trace(
    message_id: uuid.UUID, user: CurrentUser, db: DbDep
) -> RetrievalTraceResponse:
    message = db.get(Message, message_id)
    if message is None:
        raise APIError(404, "not_found", "Message not found.")
    conversation = db.get(Conversation, message.conversation_id)
    is_admin = user.role == UserRole.admin
    if conversation is None or not (is_admin or conversation.user_id == user.id):
        raise APIError(404, "not_found", "Message not found.")

    stmt = (
        select(RetrievalResult, Document.title, Chunk.page_start, Chunk.page_end, Chunk.document_id)
        .join(Chunk, Chunk.id == RetrievalResult.chunk_id)
        .join(Document, Document.id == Chunk.document_id)
        .where(RetrievalResult.message_id == message_id)
        .order_by(RetrievalResult.selected_for_context.desc(), RetrievalResult.fused_rank)
    )
    results = [
        RetrievalResultOut(
            chunk_id=rr.chunk_id,
            document_id=document_id,
            document_title=title,
            page_start=page_start,
            page_end=page_end,
            lexical_rank=rr.lexical_rank,
            dense_rank=rr.dense_rank,
            fused_rank=rr.fused_rank,
            rerank_rank=rr.rerank_rank,
            lexical_score=rr.lexical_score,
            dense_score=rr.dense_score,
            fused_score=rr.fused_score,
            rerank_score=rr.rerank_score,
            selected_for_context=rr.selected_for_context,
        )
        for rr, title, page_start, page_end, document_id in db.execute(stmt).all()
    ]
    return RetrievalTraceResponse(
        message_id=message_id, retrieval_mode=message.retrieval_mode, results=results
    )
