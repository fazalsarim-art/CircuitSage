"""Background worker: claims ingestion jobs, extracts + chunks PDFs, embeds chunks, and
upserts vectors to Qdrant.

Jobs are claimed with ``SELECT ... FOR UPDATE SKIP LOCKED`` so multiple workers never grab
the same job. A job stuck in ``processing`` past the lock timeout (a crashed worker) is
reclaimable. Failures retry up to ``max_attempts`` before a terminal failure.
"""

import logging
import os
import socket
import time
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.models.document import Chunk, Document, DocumentSource, IngestionJob
from app.db.models.enums import DocumentStatus, JobStatus
from app.db.session import SessionLocal
from app.services.chunking import CHUNKER_VERSION, chunk_pages
from app.services.documents import extract_pages
from app.services.embeddings import Embedder, build_embedder
from app.services.vector_store import VectorStore, build_vector_store

WORKER_ID = f"{socket.gethostname()}-{os.getpid()}"
LOCK_TIMEOUT = timedelta(minutes=5)
POLL_INTERVAL_SECONDS = 2.0
PARSER_VERSION = "pymupdf-1.28"

_logger = logging.getLogger("app.worker")


def claim_job(db: Session) -> IngestionJob | None:
    now = datetime.now(UTC)
    stale_before = now - LOCK_TIMEOUT
    stmt = (
        select(IngestionJob)
        .where(
            or_(
                IngestionJob.status == JobStatus.queued,
                and_(
                    IngestionJob.status == JobStatus.processing,
                    IngestionJob.locked_at < stale_before,
                ),
            )
        )
        .order_by(IngestionJob.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = db.scalar(stmt)
    if job is None:
        return None
    job.status = JobStatus.processing
    job.locked_by = WORKER_ID
    job.locked_at = now
    job.attempt += 1
    if job.started_at is None:
        job.started_at = now
    db.commit()
    return job


def process_job(
    db: Session,
    settings: Settings,
    job: IngestionJob,
    embedder: Embedder,
    vector_store: VectorStore,
) -> None:
    document = db.get(Document, job.document_id)
    if document is None:
        job.status = JobStatus.failed
        job.error_code = "document_missing"
        job.finished_at = datetime.now(UTC)
        job.locked_by = None
        db.commit()
        return

    job_id = job.id
    document_id = document.id
    owner_id = document.owner_id
    visibility = document.visibility.value
    try:
        document.status = DocumentStatus.processing
        db.flush()

        source = db.get(DocumentSource, document_id)
        if source is None:
            raise RuntimeError("stored PDF source is missing")

        drafts = chunk_pages(extract_pages(source.content))

        db.execute(Chunk.__table__.delete().where(Chunk.document_id == document_id))
        for draft in drafts:
            db.add(
                Chunk(
                    document_id=document_id,
                    ordinal=draft.ordinal,
                    heading=draft.heading,
                    content=draft.content,
                    page_start=draft.page_start,
                    page_end=draft.page_end,
                    token_count=draft.token_count,
                    checksum=draft.checksum,
                )
            )
        db.flush()

        stored_chunks = list(
            db.scalars(
                select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.ordinal)
            )
        )
        vectors = embedder.embed([chunk.content for chunk in stored_chunks])

        vector_store.ensure_collection(embedder.dimensions)
        vector_store.delete_by_document(document_id)
        vector_store.upsert_chunks(
            [
                (
                    chunk.id,
                    vector,
                    {
                        "document_id": str(document_id),
                        "owner_id": str(owner_id),
                        "visibility": visibility,
                        "page_start": chunk.page_start,
                        "page_end": chunk.page_end,
                    },
                )
                for chunk, vector in zip(stored_chunks, vectors, strict=True)
            ]
        )

        document.chunk_count = len(stored_chunks)
        document.parser_version = PARSER_VERSION
        document.chunker_version = CHUNKER_VERSION
        document.embedding_model = embedder.model
        document.embedding_dimensions = embedder.dimensions
        document.status = DocumentStatus.indexed
        document.error_code = None

        job.status = JobStatus.succeeded
        job.error_code = None
        job.error_detail = None
        job.locked_by = None
        job.finished_at = datetime.now(UTC)
        db.commit()
        _logger.info("ingestion_succeeded", extra={"event": "ingestion_succeeded"})
    except Exception as exc:  # noqa: BLE001 - failures are recorded on the job, never raised
        db.rollback()
        _fail_or_retry(db, job_id, document_id, exc)


def _fail_or_retry(db: Session, job_id: uuid.UUID, document_id: uuid.UUID, exc: Exception) -> None:
    job = db.get(IngestionJob, job_id)
    document = db.get(Document, document_id)
    if job is None:
        return
    job.error_code = "ingestion_failed"
    job.error_detail = str(exc)[:1000]
    job.locked_by = None
    job.locked_at = None
    if job.attempt >= job.max_attempts:
        job.status = JobStatus.failed
        job.finished_at = datetime.now(UTC)
        if document is not None:
            document.status = DocumentStatus.failed
            document.error_code = "ingestion_failed"
    else:
        job.status = JobStatus.queued
        if document is not None:
            document.status = DocumentStatus.queued
    db.commit()
    _logger.warning("ingestion_failed", extra={"event": "ingestion_failed"})


def run_once(
    db: Session, settings: Settings, embedder: Embedder, vector_store: VectorStore
) -> bool:
    """Claim and process a single ingestion job. Returns True if work was done."""
    job = claim_job(db)
    if job is None:
        return False
    process_job(db, settings, job, embedder, vector_store)
    return True


def process_pending_eval(
    db: Session, settings: Settings, embedder: Embedder, vector_store: VectorStore, reranker
) -> bool:
    """Claim and execute a single queued evaluation run. Returns True if work was done."""
    from app.evals.runner import claim_queued_run, execute_run

    run = claim_queued_run(db)
    if run is None:
        return False
    execute_run(db, settings, run, embedder, vector_store, reranker)
    return True


def run() -> None:  # pragma: no cover - long-running loop
    from app.retrieval.reranker import build_reranker

    configure_logging()
    settings = get_settings()
    embedder = build_embedder(settings)
    vector_store = build_vector_store(settings)
    vector_store.ensure_collection(settings.embedding_dimensions)
    reranker = build_reranker(settings)
    _logger.info("worker_started", extra={"event": "worker_started"})
    while True:
        with SessionLocal() as db:
            worked = run_once(db, settings, embedder, vector_store)
        if not worked:
            with SessionLocal() as db:
                worked = process_pending_eval(db, settings, embedder, vector_store, reranker)
        if not worked:
            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":  # pragma: no cover
    run()
