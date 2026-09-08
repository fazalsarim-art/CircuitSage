"""Document and job endpoints (§8.11)."""

import base64
import json
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from app.api.deps import AdminUser, CurrentUser
from app.core.config import Settings, get_settings
from app.core.errors import APIError
from app.db.models.document import Chunk, Document, IngestionJob
from app.db.models.enums import DocumentStatus, UserRole, Visibility
from app.db.session import get_db
from app.schemas.documents import (
    ChunkListResponse,
    ChunkPreview,
    DocumentDeletedResponse,
    DocumentListResponse,
    DocumentSummary,
    DocumentUploadResponse,
    JobStatusResponse,
)
from app.services import documents as documents_service

router = APIRouter(prefix="/documents", tags=["documents"])
jobs_router = APIRouter(prefix="/jobs", tags=["documents"])

DbDep = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]

_PREVIEW_CHARS = 500


def _encode_cursor(created_at: datetime, doc_id: uuid.UUID) -> str:
    raw = json.dumps({"c": created_at.isoformat(), "i": str(doc_id)})
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        data = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        return datetime.fromisoformat(data["c"]), uuid.UUID(data["i"])
    except Exception as exc:
        raise APIError(422, "invalid_cursor", "Invalid pagination cursor.") from exc


@router.post("", status_code=202, response_model=DocumentUploadResponse)
def upload_document(
    admin: AdminUser,
    db: DbDep,
    settings: SettingsDep,
    file: Annotated[UploadFile, File()],
    title: Annotated[str, Form()],
    source_url: Annotated[str | None, Form()] = None,
    publisher: Annotated[str | None, Form()] = None,
    visibility: Annotated[str, Form()] = "private",
) -> DocumentUploadResponse:
    title = title.strip()
    if not 1 <= len(title) <= 240:
        raise APIError(422, "invalid_metadata", "Title must be 1-240 characters.")
    try:
        visibility_enum = Visibility(visibility)
    except ValueError as exc:
        raise APIError(
            422, "invalid_metadata", "visibility must be 'private' or 'shared'."
        ) from exc

    temp_path, sha256, size = documents_service.save_upload_to_temp(file, settings.max_upload_bytes)
    try:
        document, job = documents_service.create_document(
            db,
            owner=admin,
            title=title,
            source_url=source_url,
            publisher=publisher,
            visibility=visibility_enum,
            temp_path=temp_path,
            sha256=sha256,
            size=size,
            max_pages=settings.max_pdf_pages,
        )
    finally:
        temp_path.unlink(missing_ok=True)
    return DocumentUploadResponse(document_id=document.id, job_id=job.id, status=document.status)


@router.get("", response_model=DocumentListResponse)
def list_documents(
    user: CurrentUser,
    db: DbDep,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    status: str | None = None,
    search: str | None = None,
) -> DocumentListResponse:
    stmt = select(Document)
    if user.role != UserRole.admin:
        stmt = stmt.where(
            (Document.owner_id == user.id) | (Document.visibility == Visibility.shared)
        )
    if status:
        try:
            stmt = stmt.where(Document.status == DocumentStatus(status))
        except ValueError as exc:
            raise APIError(422, "invalid_status", "Unknown document status.") from exc
    if search:
        stmt = stmt.where(Document.title.ilike(f"%{search}%"))
    if cursor:
        cur_created, cur_id = _decode_cursor(cursor)
        stmt = stmt.where(tuple_(Document.created_at, Document.id) < (cur_created, cur_id))

    stmt = stmt.order_by(Document.created_at.desc(), Document.id.desc()).limit(limit + 1)
    rows = list(db.scalars(stmt))
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = _encode_cursor(last.created_at, last.id)
        rows = rows[:limit]
    return DocumentListResponse(
        items=[DocumentSummary.model_validate(row) for row in rows], next_cursor=next_cursor
    )


@router.get("/{document_id}", response_model=DocumentSummary)
def get_document(document_id: uuid.UUID, user: CurrentUser, db: DbDep) -> DocumentSummary:
    document = documents_service.get_visible_document(db, user, document_id)
    return DocumentSummary.model_validate(document)


@router.get("/{document_id}/chunks", response_model=ChunkListResponse)
def list_chunks(
    document_id: uuid.UUID,
    user: CurrentUser,
    db: DbDep,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ChunkListResponse:
    documents_service.get_visible_document(db, user, document_id)
    after_ordinal = -1
    if cursor:
        try:
            after_ordinal = int(cursor)
        except ValueError as exc:
            raise APIError(422, "invalid_cursor", "Invalid pagination cursor.") from exc
    stmt = (
        select(Chunk)
        .where(Chunk.document_id == document_id, Chunk.ordinal > after_ordinal)
        .order_by(Chunk.ordinal)
        .limit(limit + 1)
    )
    rows = list(db.scalars(stmt))
    next_cursor = None
    if len(rows) > limit:
        next_cursor = str(rows[limit - 1].ordinal)
        rows = rows[:limit]
    items = [
        ChunkPreview(
            id=row.id,
            ordinal=row.ordinal,
            heading=row.heading,
            page_start=row.page_start,
            page_end=row.page_end,
            token_count=row.token_count,
            preview=row.content[:_PREVIEW_CHARS],
        )
        for row in rows
    ]
    return ChunkListResponse(items=items, next_cursor=next_cursor)


@router.post("/{document_id}/reindex", status_code=202, response_model=DocumentUploadResponse)
def reindex_document(
    document_id: uuid.UUID,
    admin: AdminUser,
    db: DbDep,
    chunker_version: Annotated[str | None, Form()] = None,
) -> DocumentUploadResponse:
    document = db.get(Document, document_id)
    if document is None:
        raise APIError(404, "not_found", "Document not found.")
    job = documents_service.create_reindex_job(db, document)
    return DocumentUploadResponse(document_id=document.id, job_id=job.id, status=document.status)


@router.delete("/{document_id}", status_code=202, response_model=DocumentDeletedResponse)
def delete_document(document_id: uuid.UUID, admin: AdminUser, db: DbDep) -> DocumentDeletedResponse:
    document = db.get(Document, document_id)
    if document is None:
        raise APIError(404, "not_found", "Document not found.")
    documents_service.delete_document(db, document)
    return DocumentDeletedResponse(document_id=document_id, status="deleted")


@jobs_router.get("/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: uuid.UUID, user: CurrentUser, db: DbDep) -> JobStatusResponse:
    job = db.get(IngestionJob, job_id)
    if job is None:
        raise APIError(404, "not_found", "Job not found.")
    document = db.get(Document, job.document_id)
    is_admin = user.role == UserRole.admin
    if document is None or not (is_admin or document.owner_id == user.id):
        raise APIError(404, "not_found", "Job not found.")
    return JobStatusResponse(
        id=job.id,
        document_id=job.document_id,
        status=job.status,
        attempt=job.attempt,
        max_attempts=job.max_attempts,
        error_code=job.error_code,
        error_detail=job.error_detail if is_admin else None,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )
