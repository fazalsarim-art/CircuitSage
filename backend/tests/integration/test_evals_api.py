"""Integration tests for evaluation runs: create -> execute -> metrics -> compare -> export."""

import uuid

import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy import text as sqltext

from app.core.config import get_settings
from app.db.models.benchmark import EvalRun
from app.db.models.document import Chunk
from app.db.session import SessionLocal
from app.evals import runner
from app.main import create_app
from app.worker import run_once
from tests._fakes import FakeEmbedder, FakeReranker, make_test_vector_store

PASSWORD = "password12345"
SPI_TEXT = "SPI clock polarity register mode selects the sampling edge and overrun flag. " * 10
EMBEDDER = FakeEmbedder()
RERANKER = FakeReranker()


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


def _admin(client):
    from app.cli import create_admin

    create_admin("admin@example.com", PASSWORD)
    r = client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": PASSWORD})
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def _published_benchmark(client, admin, settings, store, monkeypatch) -> str:
    monkeypatch.setattr("app.services.benchmark.MIN_CASES_FOR_PUBLISH", 1)
    client.post(
        "/api/v1/documents",
        headers=admin,
        files={"file": ("m.pdf", _pdf(SPI_TEXT), "application/pdf")},
        data={"title": "SPI Manual", "visibility": "shared"},
    )
    with SessionLocal() as db:
        while run_once(db, settings, EMBEDDER, store):
            pass
        chunk_id = str(db.scalar(select(Chunk.id)))

    version = client.post(
        "/api/v1/benchmark/versions", headers=admin, json={"name": "circuitsage"}
    ).json()
    client.post(
        f"/api/v1/benchmark/versions/{version['id']}/cases",
        headers=admin,
        json={
            "external_id": "spi-1",
            "question": "Which register selects the SPI clock polarity mode?",
            "category": "register_lookup",
            "difficulty": "medium",
            "split": "test",
            "judgments": [{"chunk_id": chunk_id, "relevance": 3}],
        },
    )
    client.post(
        f"/api/v1/benchmark/versions/{version['id']}/publish",
        headers=admin,
        json={"confirmation": "circuitsage"},
    )
    return version["id"]


def _create_and_run(client, admin, settings, store, version_id, mode):
    run = client.post(
        "/api/v1/evals/runs",
        headers=admin,
        json={"benchmark_version_id": version_id, "retrieval_mode": mode, "top_k": 10},
    ).json()
    with SessionLocal() as db:
        run_row = db.get(EvalRun, uuid.UUID(run["id"]))
        runner.execute_run(db, settings, run_row, EMBEDDER, store, RERANKER)
    return run["id"]


def test_eval_run_computes_metrics(client, settings, store, monkeypatch):
    admin = _admin(client)
    version_id = _published_benchmark(client, admin, settings, store, monkeypatch)

    run_id = _create_and_run(client, admin, settings, store, version_id, "lexical")

    detail = client.get(f"/api/v1/evals/runs/{run_id}", headers=admin).json()
    assert detail["run"]["status"] == "succeeded"
    metrics = detail["run"]["metrics"]
    assert metrics["hit_at_5"] == 1.0
    assert metrics["recall_at_5"] == 1.0
    assert metrics["mrr_at_10"] == 1.0
    assert metrics["ndcg_at_10"] == 1.0
    assert len(detail["results"]) == 1


def test_eval_run_requires_published_benchmark(client, settings, store, monkeypatch):
    admin = _admin(client)
    monkeypatch.setattr("app.services.benchmark.MIN_CASES_FOR_PUBLISH", 1)
    version = client.post(
        "/api/v1/benchmark/versions", headers=admin, json={"name": "draft"}
    ).json()
    r = client.post(
        "/api/v1/evals/runs",
        headers=admin,
        json={"benchmark_version_id": version["id"], "retrieval_mode": "lexical", "top_k": 10},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "benchmark_not_published"


def test_compare_and_export_runs(client, settings, store, monkeypatch):
    admin = _admin(client)
    version_id = _published_benchmark(client, admin, settings, store, monkeypatch)

    lexical = _create_and_run(client, admin, settings, store, version_id, "lexical")
    dense = _create_and_run(client, admin, settings, store, version_id, "dense")

    compare = client.get(
        f"/api/v1/evals/runs/compare?left_id={lexical}&right_id={dense}", headers=admin
    ).json()
    assert compare["equivalent"] is True
    assert "ndcg_at_10" in compare["metric_deltas"]

    export = client.get(f"/api/v1/evals/runs/{lexical}/export", headers=admin)
    assert export.status_code == 200
    assert export.json()["run"]["metrics"]["hit_at_5"] == 1.0
