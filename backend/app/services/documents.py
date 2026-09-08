"""Document ingestion service: safe PDF upload, validation/extraction, and queries.

Uploads are streamed to a temporary file while enforcing the byte limit and PDF magic
bytes; the temp file is the caller's responsibility to delete. Validated PDF bytes are
persisted in ``document_sources`` so the worker can extract them.
"""

import hashlib
import tempfile
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.db.models.document import (
    Chunk,
    Document,
    DocumentSource,
    IngestionJob,
)
from app.db.models.enums import DocumentStatus, JobStatus, UserRole, Visibility
from app.db.models.user import User
from app.services.chunking import PageText

_READ_CHUNK = 64 * 1024
_ACTIVE_JOB_STATUSES = (JobStatus.queued, JobStatus.processing)


def _open_pdf(data: bytes):
    try:
        import pymupdf as fitz
    except ImportError:  # pragma: no cover - depends on installed distribution
        import fitz
    return fitz.open(stream=data, filetype="pdf")


def save_upload_to_temp(upload: UploadFile, max_bytes: int) -> tuple[Path, str, int]:
    """Stream the upload to a temp file. Returns (path, sha256_hex, size). Raises APIError."""
    digest = hashlib.sha256()
    size = 0
    first = True
    fd, name = tempfile.mkstemp(suffix=".pdf")
    path = Path(name)
    try:
        with open(fd, "wb") as out:
            while True:
                data = upload.file.read(_READ_CHUNK)
                if not data:
                    break
                if first:
                    if not data.startswith(b"%PDF"):
                        raise APIError(400, "invalid_pdf", "File is not a valid PDF.")
                    first = False
                size += len(data)
                if size > max_bytes:
                    raise APIError(413, "too_large", "File exceeds the maximum allowed size.")
                digest.update(data)
                out.write(data)
        if first:
            raise APIError(400, "invalid_pdf", "Uploaded file is empty.")
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return path, digest.hexdigest(), size


def validate_pdf(path: Path, max_pages: int) -> int:
    """Validate encryption, page count, and extractable text. Returns page_count."""
    data = path.read_bytes()
    if not data.startswith(b"%PDF"):
        raise APIError(400, "invalid_pdf", "File is not a valid PDF.")
    try:
        doc = _open_pdf(data)
    except Exception as exc:
        raise APIError(400, "invalid_pdf", "File could not be parsed as a PDF.") from exc
    try:
        if getattr(doc, "needs_pass", False) or getattr(doc, "is_encrypted", False):
            raise APIError(400, "invalid_pdf", "Encrypted PDFs are not supported.")
        page_count = doc.page_count
        if page_count < 1:
            raise APIError(400, "invalid_pdf", "PDF has no pages.")
        if page_count > max_pages:
            raise APIError(400, "invalid_pdf", f"PDF exceeds the {max_pages}-page limit.")
        extractable = sum(len(doc[i].get_text("text").strip()) for i in range(page_count))
        if extractable == 0:
            raise APIError(400, "invalid_pdf", "PDF has no extractable text (image-only).")
        return page_count
    finally:
        doc.close()


def extract_pages(pdf_bytes: bytes) -> list[PageText]:
    doc = _open_pdf(pdf_bytes)
    try:
        return [PageText(i + 1, doc[i].get_text("text")) for i in range(doc.page_count)]
    finally:
        doc.close()


def create_document(
    db: Session,
    *,
    owner: User,
    title: str,
    source_url: str | None,
    publisher: str | None,
    visibility: Visibility,
    temp_path: Path,
    sha256: str,
    size: int,
    max_pages: int,
) -> tuple[Document, IngestionJob]:
    page_count = validate_pdf(temp_path, max_pages)

    duplicate = db.scalar(
        select(Document.id).where(Document.owner_id == owner.id, Document.sha256 == sha256)
    )
    if duplicate is not None:
        raise APIError(409, "duplicate", "This document has already been uploaded.")

    document = Document(
        owner_id=owner.id,
        title=title,
        source_url=source_url,
        publisher=publisher,
        sha256=sha256,
        status=DocumentStatus.queued,
        visibility=visibility,
        page_count=page_count,
    )
    db.add(document)
    db.flush()
    db.add(DocumentSource(document_id=document.id, content=temp_path.read_bytes(), byte_size=size))
    job = IngestionJob(document_id=document.id, status=JobStatus.queued)
    db.add(job)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise APIError(409, "duplicate", "This document has already been uploaded.") from exc
    db.refresh(document)
    db.refresh(job)
    return document, job


def can_view(user: User, document: Document) -> bool:
    return (
        user.role == UserRole.admin
        or document.owner_id == user.id
        or document.visibility == Visibility.shared
    )


def get_visible_document(db: Session, user: User, document_id: uuid.UUID) -> Document:
    document = db.get(Document, document_id)
    if document is None or not can_view(user, document):
        raise APIError(404, "not_found", "Document not found.")
    return document


def create_reindex_job(db: Session, document: Document) -> IngestionJob:
    active = db.scalar(
        select(IngestionJob.id).where(
            IngestionJob.document_id == document.id,
            IngestionJob.status.in_(_ACTIVE_JOB_STATUSES),
        )
    )
    if active is not None:
        raise APIError(409, "job_active", "An ingestion job is already active for this document.")
    document.status = DocumentStatus.queued
    document.error_code = None
    job = IngestionJob(document_id=document.id, status=JobStatus.queued)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def delete_document(db: Session, document: Document, vector_store=None) -> None:
    # Remove derived Qdrant points first (best-effort), then the relational rows.
    if vector_store is not None:
        vector_store.delete_by_document(document.id)
    db.execute(delete(Chunk).where(Chunk.document_id == document.id))
    db.delete(document)
    db.commit()
