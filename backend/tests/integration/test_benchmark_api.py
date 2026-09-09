"""Integration tests for benchmark authoring (versions, cases, import/export, publish)."""

import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy import text as sqltext

from app.core.config import get_settings
from app.db.models.document import Chunk
from app.db.session import SessionLocal
from app.main import create_app
from app.worker import run_once
from tests._fakes import FakeEmbedder, make_test_vector_store

PASSWORD = "password12345"
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
    vector_store.recreate_collection(FakeEmbedder().dimensions)
    return vector_store


@pytest.fixture()
def client():
    return TestClient(create_app())


@pytest.fixture(autouse=True)
def _clean():
    with SessionLocal() as db:
        db.execute(sqltext("DELETE FROM benchmark_versions"))
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


def _seed_chunk_id(client, admin, settings, store) -> str:
    client.post(
        "/api/v1/documents",
        headers=admin,
        files={"file": ("m.pdf", _pdf(SPI_TEXT), "application/pdf")},
        data={"title": "SPI Manual", "visibility": "shared"},
    )
    with SessionLocal() as db:
        while run_once(db, settings, FakeEmbedder(), store):
            pass
        return str(db.scalar(select(Chunk.id)))


def _case(external_id, chunk_id=None, category="register_lookup", relevance=3):
    payload = {
        "external_id": external_id,
        "question": "Why does the SPI status register stay busy after a read?",
        "category": category,
        "difficulty": "medium",
        "split": "test",
    }
    if chunk_id is not None:
        payload["judgments"] = [{"chunk_id": chunk_id, "relevance": relevance}]
    return payload


def test_create_version_and_case(client, settings, store):
    admin = _headers(client, "admin@example.com", admin=True)
    chunk_id = _seed_chunk_id(client, admin, settings, store)

    version = client.post(
        "/api/v1/benchmark/versions", headers=admin, json={"name": "circuitsage"}
    ).json()
    assert version["version"] == 1
    assert version["status"] == "draft"

    case = client.post(
        f"/api/v1/benchmark/versions/{version['id']}/cases",
        headers=admin,
        json=_case("uart-1", chunk_id),
    )
    assert case.status_code == 201
    assert case.json()["judgments"][0]["relevance"] == 3

    cases = client.get(f"/api/v1/benchmark/versions/{version['id']}/cases", headers=admin).json()
    assert len(cases["items"]) == 1


def test_member_cannot_create_version(client):
    member = _headers(client, "member@example.com")
    r = client.post("/api/v1/benchmark/versions", headers=member, json={"name": "x"})
    assert r.status_code == 403


def test_duplicate_case_conflict(client):
    admin = _headers(client, "admin@example.com", admin=True)
    version = client.post(
        "/api/v1/benchmark/versions", headers=admin, json={"name": "circuitsage"}
    ).json()
    url = f"/api/v1/benchmark/versions/{version['id']}/cases"
    assert client.post(url, headers=admin, json=_case("dup")).status_code == 201
    dup = client.post(url, headers=admin, json=_case("dup"))
    assert dup.status_code == 409


def test_publish_requires_minimum_cases(client):
    admin = _headers(client, "admin@example.com", admin=True)
    version = client.post(
        "/api/v1/benchmark/versions", headers=admin, json={"name": "circuitsage"}
    ).json()
    client.post(f"/api/v1/benchmark/versions/{version['id']}/cases", headers=admin, json=_case("a"))
    r = client.post(
        f"/api/v1/benchmark/versions/{version['id']}/publish",
        headers=admin,
        json={"confirmation": "circuitsage"},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "incomplete"


def test_publish_success_then_immutable(client, settings, store, monkeypatch):
    monkeypatch.setattr("app.services.benchmark.MIN_CASES_FOR_PUBLISH", 1)
    admin = _headers(client, "admin@example.com", admin=True)
    chunk_id = _seed_chunk_id(client, admin, settings, store)
    version = client.post(
        "/api/v1/benchmark/versions", headers=admin, json={"name": "circuitsage"}
    ).json()
    client.post(
        f"/api/v1/benchmark/versions/{version['id']}/cases",
        headers=admin,
        json=_case("uart-1", chunk_id, relevance=3),
    )
    published = client.post(
        f"/api/v1/benchmark/versions/{version['id']}/publish",
        headers=admin,
        json={"confirmation": "circuitsage", "source_commit": "abc1234"},
    )
    assert published.status_code == 200
    assert published.json()["status"] == "published"

    # Published versions are immutable.
    immutable = client.post(
        f"/api/v1/benchmark/versions/{version['id']}/cases",
        headers=admin,
        json=_case("uart-2", chunk_id),
    )
    assert immutable.status_code == 409
    assert immutable.json()["error"]["code"] == "published_immutable"


def test_unanswerable_case_blocks_publish_when_relevant(client, settings, store, monkeypatch):
    monkeypatch.setattr("app.services.benchmark.MIN_CASES_FOR_PUBLISH", 1)
    admin = _headers(client, "admin@example.com", admin=True)
    chunk_id = _seed_chunk_id(client, admin, settings, store)
    version = client.post(
        "/api/v1/benchmark/versions", headers=admin, json={"name": "circuitsage"}
    ).json()
    client.post(
        f"/api/v1/benchmark/versions/{version['id']}/cases",
        headers=admin,
        json=_case("bad", chunk_id, category="unanswerable", relevance=3),
    )
    r = client.post(
        f"/api/v1/benchmark/versions/{version['id']}/publish",
        headers=admin,
        json={"confirmation": "circuitsage"},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_case"


def test_import_export_roundtrip(client):
    admin = _headers(client, "admin@example.com", admin=True)
    v1 = client.post("/api/v1/benchmark/versions", headers=admin, json={"name": "imp"}).json()
    jsonl = (
        '{"external_id":"c1","question":"Why does the UART overrun flag stay set here?",'
        '"category":"troubleshooting","difficulty":"easy","split":"test"}\n'
        '{"external_id":"c2","question":"Which register controls the SPI clock mode exactly?",'
        '"category":"register_lookup","difficulty":"hard","split":"validation"}\n'
    )
    imp = client.post(
        f"/api/v1/benchmark/versions/{v1['id']}/import",
        headers=admin,
        files={"file": ("b.jsonl", jsonl.encode(), "application/x-ndjson")},
        data={"replace": "false"},
    )
    assert imp.status_code == 200
    assert imp.json()["imported"] == 2

    exported = client.get(f"/api/v1/benchmark/versions/{v1['id']}/export", headers=admin).text
    assert exported.count("\n") == 2

    v2 = client.post("/api/v1/benchmark/versions", headers=admin, json={"name": "imp2"}).json()
    reimp = client.post(
        f"/api/v1/benchmark/versions/{v2['id']}/import",
        headers=admin,
        files={"file": ("b.jsonl", exported.encode(), "application/x-ndjson")},
        data={"replace": "false"},
    )
    assert reimp.json()["imported"] == 2
