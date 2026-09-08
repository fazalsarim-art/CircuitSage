"""Integration tests for the chat/RAG pipeline (retrieval + grounded answers + trace).

Uses real Postgres + real Qdrant with deterministic fakes for the embedder, reranker, and
answer client, so the whole pipeline runs offline. Requires ``docker compose up -d``.
"""

import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text as sqltext

from app.api.deps import get_answer_client, get_embedder, get_reranker, get_vector_store
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.main import create_app
from app.services.answers import INSUFFICIENT_MARKER
from app.worker import run_once
from tests._fakes import FakeAnswerClient, FakeEmbedder, FakeReranker, make_test_vector_store

PASSWORD = "password12345"
EMBEDDER = FakeEmbedder()
RERANKER = FakeReranker()
SPI_TEXT = "SPI clock polarity register mode selects the sampling edge and overrun flag. " * 10


def _pdf(text: str) -> bytes:
    doc = pymupdf.open()
    doc.new_page().insert_textbox(pymupdf.Rect(50, 50, 545, 742), text, fontsize=10)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture()
def settings():
    return get_settings()


@pytest.fixture()
def store(settings):
    vector_store = make_test_vector_store(settings)
    vector_store.recreate_collection(EMBEDDER.dimensions)
    return vector_store


@pytest.fixture()
def answer_client():
    return FakeAnswerClient()


@pytest.fixture()
def client(store, answer_client):
    app = create_app()
    app.dependency_overrides[get_embedder] = lambda: EMBEDDER
    app.dependency_overrides[get_vector_store] = lambda: store
    app.dependency_overrides[get_reranker] = lambda: RERANKER
    app.dependency_overrides[get_answer_client] = lambda: answer_client
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean():
    with SessionLocal() as db:
        db.execute(sqltext("DELETE FROM documents"))
        db.execute(sqltext("DELETE FROM users"))
        db.commit()
    yield


def _headers(client, email, *, admin=False):
    if admin:
        from app.cli import create_admin

        create_admin(email, PASSWORD)
    else:
        client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD})
    r = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def _ingest(client, headers, settings, store, text=SPI_TEXT, title="SPI Manual"):
    client.post(
        "/api/v1/documents",
        headers=headers,
        files={"file": ("m.pdf", _pdf(text), "application/pdf")},
        data={"title": title, "visibility": "shared"},
    )
    with SessionLocal() as db:
        while run_once(db, settings, EMBEDDER, store):
            pass


def _new_conversation(client, headers):
    return client.post("/api/v1/conversations", headers=headers, json={"title": "Q"}).json()["id"]


def _ask(client, headers, conv_id, content="Why does the overrun flag stay set?", mode="hybrid"):
    return client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        headers=headers,
        json={"content": content, "retrieval_mode": mode, "top_k": 8},
    )


def test_answered_with_valid_citation(client, settings, store):
    admin = _headers(client, "admin@example.com", admin=True)
    _ingest(client, admin, settings, store)
    conv = _new_conversation(client, admin)
    r = _ask(client, admin, conv)
    assert r.status_code == 201
    body = r.json()
    assert body["answer_status"] == "answered"
    assert "[C1]" in body["assistant_message"]["content"]
    assert len(body["sources"]) == 1
    assert body["sources"][0]["label"] == "C1"


def test_reranked_hybrid_mode(client, settings, store):
    admin = _headers(client, "admin@example.com", admin=True)
    _ingest(client, admin, settings, store)
    conv = _new_conversation(client, admin)
    r = _ask(client, admin, conv, mode="reranked_hybrid")
    assert r.status_code == 201
    assert r.json()["assistant_message"]["retrieval_mode"] == "reranked_hybrid"


def test_insufficient_evidence(client, settings, store, answer_client):
    answer_client.text = INSUFFICIENT_MARKER
    admin = _headers(client, "admin@example.com", admin=True)
    _ingest(client, admin, settings, store)
    conv = _new_conversation(client, admin)
    body = _ask(client, admin, conv).json()
    assert body["answer_status"] == "insufficient_evidence"
    assert len(body["sources"]) >= 1  # closest passages still surfaced


def test_generation_failure_preserves_evidence(client, settings, store, answer_client):
    answer_client.fail = True
    admin = _headers(client, "admin@example.com", admin=True)
    _ingest(client, admin, settings, store)
    conv = _new_conversation(client, admin)
    r = _ask(client, admin, conv)
    assert r.status_code == 201
    body = r.json()
    assert body["answer_status"] == "generation_failed"
    assert len(body["sources"]) >= 1


def test_invalid_citation_from_model_fails_closed(client, settings, store, answer_client):
    answer_client.text = "The flag clears per [C9]."
    admin = _headers(client, "admin@example.com", admin=True)
    _ingest(client, admin, settings, store)
    conv = _new_conversation(client, admin)
    body = _ask(client, admin, conv).json()
    assert body["answer_status"] == "insufficient_evidence"


def test_corpus_not_ready(client):
    admin = _headers(client, "admin@example.com", admin=True)
    conv = _new_conversation(client, admin)
    r = _ask(client, admin, conv)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "corpus_not_ready"


def test_retrieval_trace_records_selected(client, settings, store):
    admin = _headers(client, "admin@example.com", admin=True)
    _ingest(client, admin, settings, store)
    conv = _new_conversation(client, admin)
    assistant_id = _ask(client, admin, conv).json()["assistant_message"]["id"]
    trace = client.get(f"/api/v1/messages/{assistant_id}/retrieval", headers=admin).json()
    assert trace["retrieval_mode"] == "hybrid"
    assert len(trace["results"]) >= 1
    assert any(row["selected_for_context"] for row in trace["results"])


def test_conversation_and_trace_ownership(client, settings, store):
    admin = _headers(client, "admin@example.com", admin=True)
    other = _headers(client, "other@example.com")
    _ingest(client, admin, settings, store)
    conv = _new_conversation(client, admin)
    assistant_id = _ask(client, admin, conv).json()["assistant_message"]["id"]

    assert client.get(f"/api/v1/conversations/{conv}", headers=other).status_code == 404
    assert (
        client.get(f"/api/v1/messages/{assistant_id}/retrieval", headers=other).status_code == 404
    )
