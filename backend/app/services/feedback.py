"""Feedback service: structured submission, admin review, corrected evidence, audit history,
and safe promotion of reviewed feedback into draft benchmark cases.

Guardrails (spec §7.11): a user's feedback never enters the benchmark automatically. Corrected
evidence and draft-case creation are explicit administrator actions, and a draft case can only be
filed against a *draft* benchmark version (enforced by the benchmark service).
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.db.models.conversation import Conversation, Message
from app.db.models.document import Chunk, Document
from app.db.models.enums import (
    FeedbackReason,
    FeedbackStatus,
    MessageRole,
    UserRole,
)
from app.db.models.feedback import Feedback, FeedbackCorrection, FeedbackEvent
from app.db.models.user import User
from app.retrieval.lexical import visibility_clause
from app.schemas.benchmark import BenchmarkCaseIn, JudgmentIn
from app.schemas.feedback import (
    CorrectionOut,
    FeedbackDetail,
    FeedbackEventOut,
    FeedbackOut,
    FeedbackReviewRequest,
    FeedbackSubmit,
)
from app.services import benchmark as benchmark_service

_REVIEW_STATUSES = {
    FeedbackStatus.resolved,
    FeedbackStatus.ignored,
    FeedbackStatus.promoted_to_draft,
}


def _log_event(
    db: Session, feedback_id: uuid.UUID, actor_id: uuid.UUID | None, action: str, note: str | None
) -> None:
    db.add(FeedbackEvent(feedback_id=feedback_id, actor_id=actor_id, action=action, note=note))


def _assistant_message(db: Session, user: User, message_id: uuid.UUID) -> Message:
    """Return the assistant message the user may rate (must own the conversation)."""
    message = db.get(Message, message_id)
    if message is None:
        raise APIError(404, "not_found", "Message not found.")
    conversation = db.get(Conversation, message.conversation_id)
    if conversation is None or conversation.user_id != user.id:
        raise APIError(404, "not_found", "Message not found.")
    if message.role != MessageRole.assistant:
        raise APIError(422, "not_assistant_message", "Feedback applies to assistant answers only.")
    return message


def _question_for(db: Session, message: Message) -> str | None:
    """The user question that produced this assistant answer (latest preceding user turn)."""
    return db.scalar(
        select(Message.content)
        .where(
            Message.conversation_id == message.conversation_id,
            Message.role == MessageRole.user,
            Message.created_at <= message.created_at,
        )
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(1)
    )


def submit_feedback(
    db: Session, user: User, message_id: uuid.UUID, payload: FeedbackSubmit
) -> Feedback:
    message = _assistant_message(db, user, message_id)
    if payload.reason is not None and payload.reason not in {r.value for r in FeedbackReason}:
        raise APIError(422, "invalid_reason", "Unknown feedback reason.")

    existing = db.scalar(
        select(Feedback).where(
            Feedback.user_id == user.id, Feedback.message_id == message.id
        )
    )
    if existing is None:
        feedback = Feedback(
            message_id=message.id,
            user_id=user.id,
            rating=payload.rating,
            reason=FeedbackReason(payload.reason) if payload.reason else None,
            comment=payload.comment,
            status=FeedbackStatus.unresolved,
        )
        db.add(feedback)
        db.flush()
        _log_event(db, feedback.id, user.id, "submitted", None)
    else:
        existing.rating = payload.rating
        existing.reason = FeedbackReason(payload.reason) if payload.reason else None
        existing.comment = payload.comment
        feedback = existing
        _log_event(db, feedback.id, user.id, "updated", None)
    db.commit()
    db.refresh(feedback)
    return feedback


def list_feedback(
    db: Session,
    status: str | None = None,
    reason: str | None = None,
    rating: int | None = None,
) -> list[Feedback]:
    stmt = select(Feedback).order_by(Feedback.created_at.desc(), Feedback.id.desc())
    if status is not None:
        if status not in {s.value for s in FeedbackStatus}:
            raise APIError(422, "invalid_status", "Unknown feedback status.")
        stmt = stmt.where(Feedback.status == FeedbackStatus(status))
    if reason is not None:
        if reason not in {r.value for r in FeedbackReason}:
            raise APIError(422, "invalid_reason", "Unknown feedback reason.")
        stmt = stmt.where(Feedback.reason == FeedbackReason(reason))
    if rating is not None:
        stmt = stmt.where(Feedback.rating == rating)
    return list(db.scalars(stmt))


def get_feedback(db: Session, feedback_id: uuid.UUID) -> Feedback:
    feedback = db.get(Feedback, feedback_id)
    if feedback is None:
        raise APIError(404, "not_found", "Feedback not found.")
    return feedback


def _corrections_out(db: Session, feedback_id: uuid.UUID) -> list[CorrectionOut]:
    rows = db.execute(
        select(
            FeedbackCorrection.chunk_id,
            FeedbackCorrection.relevance,
            Document.title,
            Chunk.page_start,
            Chunk.page_end,
        )
        .join(Chunk, Chunk.id == FeedbackCorrection.chunk_id)
        .join(Document, Document.id == Chunk.document_id)
        .where(FeedbackCorrection.feedback_id == feedback_id)
        .order_by(FeedbackCorrection.relevance.desc())
    ).all()
    return [
        CorrectionOut(
            chunk_id=chunk_id,
            relevance=relevance,
            document_title=title,
            page_start=page_start,
            page_end=page_end,
        )
        for chunk_id, relevance, title, page_start, page_end in rows
    ]


def feedback_out(db: Session, feedback: Feedback) -> FeedbackOut:
    message = db.get(Message, feedback.message_id)
    question = _question_for(db, message) if message is not None else None
    return FeedbackOut(
        id=feedback.id,
        message_id=feedback.message_id,
        user_id=feedback.user_id,
        rating=feedback.rating,
        reason=feedback.reason.value if feedback.reason else None,
        comment=feedback.comment,
        status=feedback.status.value,
        reviewed_by=feedback.reviewed_by,
        reviewed_at=feedback.reviewed_at,
        resolution_note=feedback.resolution_note,
        created_at=feedback.created_at,
        updated_at=feedback.updated_at,
        question=question,
        answer=message.content if message is not None else None,
        answer_status=message.answer_status.value
        if message is not None and message.answer_status
        else None,
        retrieval_mode=message.retrieval_mode.value
        if message is not None and message.retrieval_mode
        else None,
        corrections=_corrections_out(db, feedback.id),
    )


def list_events(db: Session, feedback_id: uuid.UUID) -> list[FeedbackEventOut]:
    rows = db.scalars(
        select(FeedbackEvent)
        .where(FeedbackEvent.feedback_id == feedback_id)
        .order_by(FeedbackEvent.created_at, FeedbackEvent.id)
    )
    return [
        FeedbackEventOut(
            id=e.id, action=e.action, actor_id=e.actor_id, note=e.note, created_at=e.created_at
        )
        for e in rows
    ]


def feedback_detail(db: Session, feedback: Feedback) -> FeedbackDetail:
    base = feedback_out(db, feedback)
    return FeedbackDetail(**base.model_dump(), events=list_events(db, feedback.id))


def _replace_corrections(db: Session, feedback: Feedback, corrections) -> None:
    """Validate corrected chunks are visible to the feedback owner, then replace the rows."""
    owner = db.get(User, feedback.user_id)
    clause = visibility_clause(owner) if owner is not None else None
    db.execute(delete(FeedbackCorrection).where(FeedbackCorrection.feedback_id == feedback.id))
    for correction in corrections:
        stmt = (
            select(Chunk.id)
            .join(Document, Document.id == Chunk.document_id)
            .where(Chunk.id == correction.chunk_id)
        )
        if clause is not None:
            stmt = stmt.where(clause)
        if db.scalar(stmt) is None:
            raise APIError(
                422,
                "invalid_correction",
                f"Chunk {correction.chunk_id} is not visible to the feedback author.",
            )
        db.add(
            FeedbackCorrection(
                feedback_id=feedback.id,
                chunk_id=correction.chunk_id,
                relevance=correction.relevance,
            )
        )
    db.flush()


def _promote_to_draft(
    db: Session, admin: User, feedback: Feedback, spec, question: str | None
) -> None:
    if spec is None:
        raise APIError(422, "draft_spec_required", "A draft target is required to promote.")
    if not question:
        raise APIError(422, "no_question", "The rated answer has no originating question.")
    corrections = _corrections_out(db, feedback.id)
    if not corrections:
        raise APIError(
            422, "no_corrections", "Add corrected evidence before promoting to a draft case."
        )
    version = benchmark_service.get_version(db, spec.benchmark_version_id)
    case_in = BenchmarkCaseIn(
        external_id=spec.external_id,
        question=question,
        category=spec.category,
        difficulty=spec.difficulty,
        split=spec.split,
        expected_answer=None,
        notes=f"Promoted from feedback {feedback.id}.",
        judgments=[JudgmentIn(chunk_id=c.chunk_id, relevance=c.relevance) for c in corrections],
    )
    # add_case enforces draft-only (409 published_immutable), duplicate external_id (409),
    # and chunk existence (422) — the same safe path used by manual authoring.
    benchmark_service.add_case(db, admin, version, case_in)


def review_feedback(
    db: Session, admin: User, feedback: Feedback, payload: FeedbackReviewRequest
) -> Feedback:
    if payload.status not in {s.value for s in _REVIEW_STATUSES}:
        raise APIError(
            422, "invalid_status", "Status must be resolved, ignored, or promoted_to_draft."
        )
    status = FeedbackStatus(payload.status)

    message = db.get(Message, feedback.message_id)
    question = _question_for(db, message) if message is not None else None

    if payload.corrections is not None:
        _replace_corrections(db, feedback, payload.corrections)
        _log_event(db, feedback.id, admin.id, "corrections_updated", None)

    if status == FeedbackStatus.promoted_to_draft:
        # add_case commits the session; corrections above are flushed and included.
        _promote_to_draft(db, admin, feedback, payload.draft, question)

    feedback.status = status
    feedback.reviewed_by = admin.id
    feedback.reviewed_at = datetime.now(UTC)
    feedback.resolution_note = payload.resolution_note
    _log_event(db, feedback.id, admin.id, payload.status, payload.resolution_note)
    db.commit()
    db.refresh(feedback)
    return feedback


def is_admin(user: User) -> bool:
    return user.role == UserRole.admin
