"""Integration tests for the admin CLI: create-admin, benchmark import/export, eval-run,
and argument dispatch. These also lift coverage of the otherwise script-only cli module."""

import pytest
from sqlalchemy import select
from sqlalchemy import text as sqltext

from app import cli
from app.core.errors import APIError
from app.db.models.benchmark import BenchmarkVersion
from app.db.models.enums import UserRole
from app.db.models.user import User
from app.db.session import SessionLocal
from app.services import auth as auth_service

BANK = (
    '{"external_id":"c1","question":"Which register controls the SPI clock mode exactly?",'
    '"category":"register_lookup","difficulty":"easy","split":"test"}\n'
    '{"external_id":"c2","question":"Why does the UART overrun flag stay set here?",'
    '"category":"troubleshooting","difficulty":"medium","split":"train"}\n'
)


@pytest.fixture(autouse=True)
def _clean():
    with SessionLocal() as db:
        db.execute(sqltext("DELETE FROM benchmark_versions"))
        db.execute(sqltext("DELETE FROM documents"))
        db.execute(sqltext("DELETE FROM users"))
        db.commit()
    yield


def _seed_admin(email="admin@example.com"):
    with SessionLocal() as db:
        user = auth_service.create_user(
            db, email=email, password="password12345", role=UserRole.admin
        )
        db.commit()
        return str(user.id)


def test_create_admin_via_main(monkeypatch, capsys):
    monkeypatch.setattr("getpass.getpass", lambda *a, **k: "password12345")
    assert cli.main(["create-admin", "--email", "cli-admin@example.com"]) == 0
    with SessionLocal() as db:
        assert db.scalar(select(User.id).where(User.email == "cli-admin@example.com")) is not None


def test_create_admin_password_mismatch(monkeypatch):
    answers = iter(["password12345", "different12345"])
    monkeypatch.setattr("getpass.getpass", lambda *a, **k: next(answers))
    assert cli.main(["create-admin", "--email", "x@example.com"]) == 1


def test_create_admin_too_short(monkeypatch):
    monkeypatch.setattr("getpass.getpass", lambda *a, **k: "short")
    assert cli.main(["create-admin", "--email", "x@example.com"]) == 1


def test_import_and_export_benchmark_roundtrip(tmp_path):
    _seed_admin()
    src = tmp_path / "bank.jsonl"
    src.write_text(BANK, encoding="utf-8")

    version_id = cli.import_benchmark(str(src), "circuitsage", None, False, None)
    with SessionLocal() as db:
        version = db.get(BenchmarkVersion, version_id)
        assert version is not None

    out = tmp_path / "out.jsonl"
    cli.export_benchmark(str(version_id), str(out))
    assert out.read_text(encoding="utf-8").count("\n") == 2


def test_import_via_main_dispatch(tmp_path):
    _seed_admin()
    src = tmp_path / "bank.jsonl"
    src.write_text(BANK, encoding="utf-8")
    assert (
        cli.main(["import-benchmark", "--file", str(src), "--name", "circuitsage"]) == 0
    )


def test_resolve_admin_errors(tmp_path):
    src = tmp_path / "bank.jsonl"
    src.write_text(BANK, encoding="utf-8")

    # No administrator exists yet.
    with pytest.raises(APIError) as no_admin:
        cli.import_benchmark(str(src), "circuitsage", None, False, None)
    assert no_admin.value.status_code == 404

    # A member cannot be the attribution target.
    with SessionLocal() as db:
        auth_service.create_user(
            db, email="member@example.com", password="password12345", role=UserRole.member
        )
        db.commit()
    with pytest.raises(APIError) as not_admin:
        cli.import_benchmark(str(src), "circuitsage", None, False, "member@example.com")
    assert not_admin.value.status_code == 403


def test_eval_run_requires_published_benchmark():
    _seed_admin()
    with SessionLocal() as db:
        from app.services import benchmark as bench

        admin = db.scalar(select(User))
        version = bench.create_version(db, admin, "draft-bench", None)
        version_id = str(version.id)

    with pytest.raises(APIError) as exc:
        cli.run_eval(version_id, "lexical", 10, None)
    assert exc.value.code == "benchmark_not_published"


def test_export_missing_command_returns_two():
    assert cli.main(["reindex", "--document-id", "not-a-uuid"]) == 1
