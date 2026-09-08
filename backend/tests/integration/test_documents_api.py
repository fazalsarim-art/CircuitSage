"""Integration tests for the document ingestion API and worker.

Requires ``docker compose up -d``. PDFs are generated in-memory with PyMuPDF.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text as sqltext

from app.api.deps import get_vector_store
from app.core.config import get_settings
from app.db.models.document import Document, IngestionJob
from app.db.models.enums import JobStatus
from app.db.session import SessionLocal
from app.main import create_app
from app.worker import run_once
from tests._fakes import FakeEmbedder, make_test_vector_store

PASSWORD = "password12345"
_PARA = (
    "The SPI status register indicates whether the peripheral is currently busy. "
    "The UART overrun flag is cleared by reading the receive data register. "
    "Configure the clock polarity and phase before enabling the transfer. "
) * 4


def _make_pdf(page_texts: list[str]) -> bytes:
    doc = pymupdf.open()
    for body in page_texts:
        page = doc.new_page()
        rect = pymupdf.Rect(50, 50, page.rect.width - 50, page.rect.height - 50)
        page.insert_textbox(rect, body, fontsize=10)
    data = doc.tobytes()
    doc.close()
    return data


def _make_image_only_pdf() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.draw_rect(pymupdf.Rect(50, 50, 200, 200), fill=(0.4, 0.4, 0.4))
    data = doc.tobytes()
    doc.close()
    return data


def _make_encrypted_pdf() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "secret protected content about registers")
    data = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="user")
    doc.close()
    return data


@pytest.fixture()
def client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_vector_store] = lambda: make_test_vector_store(get_settings())
    return TestClient(app)


@pytest.fixture()
def settings():
    return get_settings()


@pytest.fixture(autouse=True)
def _clean():
    with SessionLocal() as db:
        db.execute(sqltext("DELETE FROM documents"))
        db.execute(sqltext("DELETE FROM refresh_tokens"))
        db.execute(sqltext("DELETE FROM users"))
        db.commit()
    yield


def _headers(client: TestClient, email: str, *, admin: bool = False) -> dict:
    if admin:
        from app.cli import create_admin

        create_admin(email, PASSWORD)
    else:
        client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD})
    r = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def _upload(client, headers, pdf_bytes, *, title="Sample Manual", visibility="private"):
    return client.post(
        "/api/v1/documents",
        headers=headers,
        files={"file": ("m.pdf", pdf_bytes, "application/pdf")},
        data={"title": title, "visibility": visibility},
    )


def _process_all(settings):
    embedder = FakeEmbedder()
    store = make_test_vector_store(settings)
    with SessionLocal() as db:
        while run_once(db, settings, embedder, store):
            pass


def test_upload_indexes_and_creates_chunks(client, settings):
    admin = _headers(client, "admin@example.com", admin=True)
    r = _upload(client, admin, _make_pdf([_PARA, _PARA, _PARA]))
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "queued"
    document_id, job_id = body["document_id"], body["job_id"]

    _process_all(settings)

    doc = client.get(f"/api/v1/documents/{document_id}", headers=admin).json()
    assert doc["status"] == "indexed"
    assert doc["page_count"] == 3
    assert doc["chunk_count"] >= 1

    chunks = client.get(f"/api/v1/documents/{document_id}/chunks", headers=admin).json()
    assert len(chunks["items"]) == doc["chunk_count"]
    assert chunks["items"][0]["preview"]

    job = client.get(f"/api/v1/jobs/{job_id}", headers=admin).json()
    assert job["status"] == "succeeded"


def test_upload_requires_admin(client):
    member = _headers(client, "member@example.com")
    r = _upload(client, member, _make_pdf([_PARA]))
    assert r.status_code == 403


def test_duplicate_upload_conflict(client):
    admin = _headers(client, "admin@example.com", admin=True)
    pdf = _make_pdf([_PARA])
    assert _upload(client, admin, pdf).status_code == 202
    dup = _upload(client, admin, pdf)
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "duplicate"


def test_non_pdf_rejected(client):
    admin = _headers(client, "admin@example.com", admin=True)
    r = client.post(
        "/api/v1/documents",
        headers=admin,
        files={"file": ("x.pdf", b"this is not a pdf", "application/pdf")},
        data={"title": "Fake"},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_pdf"


def test_image_only_pdf_rejected(client):
    admin = _headers(client, "admin@example.com", admin=True)
    r = _upload(client, admin, _make_image_only_pdf())
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_pdf"


def test_encrypted_pdf_rejected(client):
    admin = _headers(client, "admin@example.com", admin=True)
    r = _upload(client, admin, _make_encrypted_pdf())
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_pdf"


def test_oversized_upload_rejected(client):
    admin = _headers(client, "admin@example.com", admin=True)

    def _tiny_limit():
        return get_settings().model_copy(update={"max_upload_bytes": 100})

    client.app.dependency_overrides[get_settings] = _tiny_limit
    try:
        r = _upload(client, admin, _make_pdf([_PARA]))
        assert r.status_code == 413
        assert r.json()["error"]["code"] == "too_large"
    finally:
        client.app.dependency_overrides.clear()


def test_member_cannot_see_private_but_can_see_shared(client, settings):
    admin = _headers(client, "admin@example.com", admin=True)
    member = _headers(client, "member@example.com")

    private = _upload(client, admin, _make_pdf([_PARA]), visibility="private").json()
    shared = _upload(client, admin, _make_pdf([_PARA + "distinct"]), visibility="shared").json()

    assert (
        client.get(f"/api/v1/documents/{private['document_id']}", headers=member).status_code == 404
    )
    assert (
        client.get(f"/api/v1/documents/{shared['document_id']}", headers=member).status_code == 200
    )


def test_reindex_and_delete(client, settings):
    admin = _headers(client, "admin@example.com", admin=True)
    doc_id = _upload(client, admin, _make_pdf([_PARA, _PARA])).json()["document_id"]
    _process_all(settings)

    reindex = client.post(f"/api/v1/documents/{doc_id}/reindex", headers=admin)
    assert reindex.status_code == 202
    _process_all(settings)
    assert client.get(f"/api/v1/documents/{doc_id}", headers=admin).json()["status"] == "indexed"

    deleted = client.delete(f"/api/v1/documents/{doc_id}", headers=admin)
    assert deleted.status_code == 202
    assert client.get(f"/api/v1/documents/{doc_id}", headers=admin).status_code == 404


def test_worker_reclaims_stale_job(client, settings):
    admin = _headers(client, "admin@example.com", admin=True)
    up = _upload(client, admin, _make_pdf([_PARA])).json()

    # Simulate a crashed worker: job stuck in processing with an old lock.
    with SessionLocal() as db:
        job = db.get(IngestionJob, uuid.UUID(up["job_id"]))
        job.status = JobStatus.processing
        job.locked_by = "dead-worker"
        job.locked_at = datetime.now(UTC) - timedelta(minutes=10)
        job.attempt = 1
        db.commit()

    _process_all(settings)

    with SessionLocal() as db:
        document = db.get(Document, uuid.UUID(up["document_id"]))
        assert document.status.value == "indexed"
