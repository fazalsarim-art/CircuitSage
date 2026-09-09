"""Integration tests for the feedback loop: submit, review, corrected evidence, draft promotion.

Covers the spec's required flows: positive, negative, duplicate, unauthorized, corrected-evidence,
resolve, ignore, and draft-case creation.
"""

import uuid

import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy import text as sqltext

from app.core.config import get_settings
from app.db.models.conversation import Conversation, Message
from app.db.models.document import Chunk
from app.db.models.enums import AnswerStatus, MessageRole, RetrievalMode
from app.db.session import SessionLocal
from app.main import create_app
from app.worker import run_once
from tests._fakes import FakeEmbedder, make_test_vector_store

PASSWORD = "password12345"
SPI_TEXT = "SPI clock polarity register mode selects the sampling edge and overrun flag. " * 10
QUESTION = "Which register selects the SPI clock polarity mode?"


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
        db.execute(sqltext("DELETE FROM conversations"))
        db.execute(sqltext("DELETE FROM documents"))
        db.execute(sqltext("DELETE FROM users"))
        db.commit()
    yield


def _admin(client):
    from app.cli import create_admin

    create_admin("admin@example.com", PASSWORD)
    r = client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": PASSWORD})
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def _member(client, email="member@example.com"):
    client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD})
    r = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    token = r.json()["access_token"]
    with SessionLocal() as db:
        from app.core.security import normalize_email
        from app.db.models.user import User

        user_id = db.scalar(select(User.id).where(User.email == normalize_email(email)))
    return {"Authorization": "Bearer " + token}, user_id


def _seed_chunk(client, admin, settings, store) -> str:
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


def _seed_answer(user_id) -> tuple[str, str]:
    """Insert a conversation with a user question and an assistant answer owned by user_id."""
    with SessionLocal() as db:
        conversation = Conversation(user_id=uuid.UUID(str(user_id)), title="SPI help")
        db.add(conversation)
        db.flush()
        user_msg = Message(
            conversation_id=conversation.id,
            role=MessageRole.user,
            content=QUESTION,
            request_id=uuid.uuid4(),
        )
        db.add(user_msg)
        db.flush()
        assistant = Message(
            conversation_id=conversation.id,
            role=MessageRole.assistant,
            content="The CPOL/CPHA bits in the SPI control register select the mode. [C1]",
            retrieval_mode=RetrievalMode.lexical,
            answer_status=AnswerStatus.answered,
            request_id=uuid.uuid4(),
        )
        db.add(assistant)
        db.commit()
        return str(assistant.id), str(user_msg.id)


def test_submit_positive_and_admin_sees_it(client, settings, store):
    admin = _admin(client)
    member, member_id = _member(client)
    _seed_chunk(client, admin, settings, store)
    assistant_id, _ = _seed_answer(member_id)

    r = client.put(
        f"/api/v1/messages/{assistant_id}/feedback", headers=member, json={"rating": 1}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["rating"] == 1
    assert body["status"] == "unresolved"
    assert body["question"] == QUESTION

    listing = client.get("/api/v1/feedback", headers=admin).json()
    assert len(listing["items"]) == 1

    detail = client.get(f"/api/v1/feedback/{body['id']}", headers=admin).json()
    assert [e["action"] for e in detail["events"]] == ["submitted"]


def test_submit_negative_with_reason_and_invalid_reason(client, settings, store):
    _admin(client)
    member, member_id = _member(client)
    assistant_id, _ = _seed_answer(member_id)

    r = client.put(
        f"/api/v1/messages/{assistant_id}/feedback",
        headers=member,
        json={"rating": 0, "reason": "retrieval_miss", "comment": "Missed the CPOL section."},
    )
    assert r.status_code == 200
    assert r.json()["reason"] == "retrieval_miss"

    bad = client.put(
        f"/api/v1/messages/{assistant_id}/feedback",
        headers=member,
        json={"rating": 0, "reason": "nonsense"},
    )
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "invalid_reason"


def test_duplicate_feedback_upserts(client, settings, store):
    admin = _admin(client)
    member, member_id = _member(client)
    assistant_id, _ = _seed_answer(member_id)

    client.put(f"/api/v1/messages/{assistant_id}/feedback", headers=member, json={"rating": 1})
    second = client.put(
        f"/api/v1/messages/{assistant_id}/feedback", headers=member, json={"rating": 0}
    )
    assert second.status_code == 200
    assert second.json()["rating"] == 0

    listing = client.get("/api/v1/feedback", headers=admin).json()
    assert len(listing["items"]) == 1  # still a single row per (user, message)


def test_unauthorized_flows(client, settings, store):
    _admin(client)
    member, member_id = _member(client)
    other, _ = _member(client, "other@example.com")
    assistant_id, user_msg_id = _seed_answer(member_id)

    # A member cannot list the admin review queue.
    assert client.get("/api/v1/feedback", headers=member).status_code == 403

    # A different member cannot rate a message in a conversation they do not own.
    foreign = client.put(
        f"/api/v1/messages/{assistant_id}/feedback", headers=other, json={"rating": 1}
    )
    assert foreign.status_code == 404

    # Feedback only applies to assistant answers, not user turns.
    on_user = client.put(
        f"/api/v1/messages/{user_msg_id}/feedback", headers=member, json={"rating": 1}
    )
    assert on_user.status_code == 422
    assert on_user.json()["error"]["code"] == "not_assistant_message"


def test_review_resolve_and_ignore(client, settings, store):
    admin = _admin(client)
    member, member_id = _member(client)
    assistant_id, _ = _seed_answer(member_id)
    fb_id = client.put(
        f"/api/v1/messages/{assistant_id}/feedback", headers=member, json={"rating": 0}
    ).json()["id"]

    resolved = client.post(
        f"/api/v1/feedback/{fb_id}/review",
        headers=admin,
        json={"status": "resolved", "resolution_note": "Fixed by reindex."},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["reviewed_by"] is not None
    assert "resolved" in [e["action"] for e in resolved.json()["events"]]

    ignored = client.post(
        f"/api/v1/feedback/{fb_id}/review", headers=admin, json={"status": "ignored"}
    )
    assert ignored.json()["status"] == "ignored"

    # Members cannot review.
    assert (
        client.post(
            f"/api/v1/feedback/{fb_id}/review", headers=member, json={"status": "resolved"}
        ).status_code
        == 403
    )


def test_corrected_evidence(client, settings, store):
    admin = _admin(client)
    member, member_id = _member(client)
    chunk_id = _seed_chunk(client, admin, settings, store)
    assistant_id, _ = _seed_answer(member_id)
    fb_id = client.put(
        f"/api/v1/messages/{assistant_id}/feedback", headers=member, json={"rating": 0}
    ).json()["id"]

    reviewed = client.post(
        f"/api/v1/feedback/{fb_id}/review",
        headers=admin,
        json={
            "status": "resolved",
            "corrections": [{"chunk_id": chunk_id, "relevance": 3}],
        },
    )
    assert reviewed.status_code == 200
    corrections = reviewed.json()["corrections"]
    assert len(corrections) == 1
    assert corrections[0]["relevance"] == 3
    assert corrections[0]["document_title"] == "SPI Manual"

    bad = client.post(
        f"/api/v1/feedback/{fb_id}/review",
        headers=admin,
        json={
            "status": "resolved",
            "corrections": [{"chunk_id": str(uuid.uuid4()), "relevance": 2}],
        },
    )
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "invalid_correction"


def test_promote_to_draft_case(client, settings, store):
    admin = _admin(client)
    member, member_id = _member(client)
    chunk_id = _seed_chunk(client, admin, settings, store)
    assistant_id, _ = _seed_answer(member_id)
    fb_id = client.put(
        f"/api/v1/messages/{assistant_id}/feedback",
        headers=member,
        json={"rating": 0, "reason": "retrieval_miss"},
    ).json()["id"]

    version = client.post(
        "/api/v1/benchmark/versions", headers=admin, json={"name": "circuitsage"}
    ).json()

    # Promotion without corrected evidence is refused (nothing to judge against).
    empty = client.post(
        f"/api/v1/feedback/{fb_id}/review",
        headers=admin,
        json={
            "status": "promoted_to_draft",
            "draft": {
                "benchmark_version_id": version["id"],
                "external_id": "fb-spi-1",
                "category": "register_lookup",
            },
        },
    )
    assert empty.status_code == 422
    assert empty.json()["error"]["code"] == "no_corrections"

    promoted = client.post(
        f"/api/v1/feedback/{fb_id}/review",
        headers=admin,
        json={
            "status": "promoted_to_draft",
            "corrections": [{"chunk_id": chunk_id, "relevance": 3}],
            "draft": {
                "benchmark_version_id": version["id"],
                "external_id": "fb-spi-1",
                "category": "register_lookup",
                "difficulty": "medium",
                "split": "test",
            },
        },
    )
    assert promoted.status_code == 200
    assert promoted.json()["status"] == "promoted_to_draft"

    # A draft case now exists in that version, built from the question + corrected evidence.
    cases = client.get(
        f"/api/v1/benchmark/versions/{version['id']}/cases", headers=admin
    ).json()["items"]
    assert len(cases) == 1
    assert cases[0]["external_id"] == "fb-spi-1"
    assert cases[0]["question"] == QUESTION
    assert cases[0]["judgments"][0]["relevance"] == 3
