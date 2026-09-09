"""Feedback endpoints (§7.11): user submission plus admin failure review and promotion."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import AdminUser, CurrentUser
from app.db.models.enums import FeedbackReason
from app.db.session import get_db
from app.schemas.feedback import (
    FeedbackDetail,
    FeedbackListResponse,
    FeedbackOut,
    FeedbackReviewRequest,
    FeedbackSubmit,
)
from app.services import feedback as feedback_service

router = APIRouter(prefix="/feedback", tags=["feedback"])
messages_router = APIRouter(prefix="/messages", tags=["feedback"])

DbDep = Annotated[Session, Depends(get_db)]


@messages_router.put("/{message_id}/feedback", response_model=FeedbackOut)
def submit_feedback(
    message_id: uuid.UUID, payload: FeedbackSubmit, user: CurrentUser, db: DbDep
) -> FeedbackOut:
    feedback = feedback_service.submit_feedback(db, user, message_id, payload)
    return feedback_service.feedback_out(db, feedback)


@router.get("/reasons")
def list_reasons(user: CurrentUser) -> dict[str, list[str]]:
    """The failure taxonomy used to categorize negative feedback."""
    return {"reasons": [r.value for r in FeedbackReason]}


@router.get("", response_model=FeedbackListResponse)
def list_feedback(
    admin: AdminUser,
    db: DbDep,
    status: str | None = None,
    reason: str | None = None,
    rating: int | None = None,
) -> FeedbackListResponse:
    rows = feedback_service.list_feedback(db, status=status, reason=reason, rating=rating)
    return FeedbackListResponse(items=[feedback_service.feedback_out(db, f) for f in rows])


@router.get("/{feedback_id}", response_model=FeedbackDetail)
def get_feedback(feedback_id: uuid.UUID, admin: AdminUser, db: DbDep) -> FeedbackDetail:
    feedback = feedback_service.get_feedback(db, feedback_id)
    return feedback_service.feedback_detail(db, feedback)


@router.post("/{feedback_id}/review", response_model=FeedbackDetail)
def review_feedback(
    feedback_id: uuid.UUID, payload: FeedbackReviewRequest, admin: AdminUser, db: DbDep
) -> FeedbackDetail:
    feedback = feedback_service.get_feedback(db, feedback_id)
    reviewed = feedback_service.review_feedback(db, admin, feedback, payload)
    return feedback_service.feedback_detail(db, reviewed)
