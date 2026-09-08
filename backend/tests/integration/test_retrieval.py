"""Integration tests for lexical and dense retrieval.

Uses the real local Qdrant with a dedicated test collection and a deterministic fake
embedder (so dense ranking is reproducible offline). Requires ``docker compose up -d``.
"""

import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text as sqltext

from app.api.deps import get_embedder, get_vector_store
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.main import create_app
from app.services.vector_store import CollectionDimensionMismatch
from app.worker import run_once
from tests._fakes import FakeEmbedder, make_test_vector_store

PASSWORD = "password12345"
EMBEDDER = FakeEmbedder()
SPI_TEXT = "SPI clock polarity register mode selects the sampling edge. " * 10
UART_TEXT = "UART overrun flag receive data register buffer clears on read. " * 10


def _pdf(text: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_textbox(pymupdf.Rect(50, 50, 545, 742), text, fontsize=10)
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
def client(store):
    app = create_app()
    app.dependency_overrides[get_embedder] = lambda: EMBEDDER
    app.dependency_overrides[get_vector_store] = lambda: store
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean():
    with SessionLocal() as db:
        db.execute(sqltext("DELETE FROM documents"))
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


def _ingest(client, headers, settings, store, text, *, title="Doc", visibility="shared"):
    client.post(
        "/api/v1/documents",
        headers=headers,
        files={"file": ("m.pdf", _pdf(text), "application/pdf")},
        data={"title": title, "visibility": visibility},
    )
    with SessionLocal() as db:
        while run_once(db, settings, EMBEDDER, store):
            pass


def _search(client, headers, query, mode, top_k=5):
    return client.post(
        "/api/v1/retrieval/search",
        headers=headers,
        json={"query": query, "mode": mode, "top_k": top_k},
    )


def test_lexical_search_finds_term(client, settings, store):
    admin = _headers(client, "admin@example.com", admin=True)
    _ingest(client, admin, settings, store, SPI_TEXT, title="SPI Manual")
    r = _search(client, admin, "SPI polarity", "lexical")
    assert r.status_code == 200
    hits = r.json()["hits"]
    assert len(hits) >= 1
    assert hits[0]["document_title"] == "SPI Manual"
    assert hits[0]["score"] > 0


def test_dense_search_ranks_related_chunk_first(client, settings, store):
    admin = _headers(client, "admin@example.com", admin=True)
    _ingest(client, admin, settings, store, SPI_TEXT, title="SPI Manual")
    _ingest(client, admin, settings, store, UART_TEXT, title="UART Manual")
    r = _search(client, admin, "clock polarity sampling edge", "dense")
    assert r.status_code == 200
    hits = r.json()["hits"]
    assert len(hits) >= 1
    assert hits[0]["document_title"] == "SPI Manual"


def test_visibility_filter_on_search(client, settings, store):
    admin = _headers(client, "admin@example.com", admin=True)
    member = _headers(client, "member@example.com")
    _ingest(client, admin, settings, store, SPI_TEXT, title="Private SPI", visibility="private")
    _ingest(client, admin, settings, store, UART_TEXT, title="Shared UART", visibility="shared")

    lexical = _search(client, member, "UART overrun register", "lexical")
    titles = [h["document_title"] for h in lexical.json()["hits"]]
    assert "Shared UART" in titles
    assert "Private SPI" not in titles

    dense = _search(client, member, "clock polarity register", "dense")
    dense_titles = [h["document_title"] for h in dense.json()["hits"]]
    assert "Private SPI" not in dense_titles


def test_corpus_empty_returns_400(client):
    admin = _headers(client, "admin@example.com", admin=True)
    r = _search(client, admin, "anything", "lexical")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "corpus_empty"


def test_invalid_mode_returns_422(client, settings, store):
    admin = _headers(client, "admin@example.com", admin=True)
    _ingest(client, admin, settings, store, SPI_TEXT)
    r = _search(client, admin, "spi", "banana")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_mode"


def test_hybrid_mode_fuses_results(client, settings, store):
    admin = _headers(client, "admin@example.com", admin=True)
    _ingest(client, admin, settings, store, SPI_TEXT, title="SPI Manual")
    r = _search(client, admin, "SPI clock polarity", "hybrid")
    assert r.status_code == 200
    assert len(r.json()["hits"]) >= 1
    assert r.json()["hits"][0]["document_title"] == "SPI Manual"


def test_collection_dimension_mismatch_refused(store):
    with pytest.raises(CollectionDimensionMismatch):
        store.ensure_collection(512)
