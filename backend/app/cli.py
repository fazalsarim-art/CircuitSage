"""Command-line administration for CircuitSage.

Usage:
    python -m app.cli create-admin --email admin@example.com

The password is read interactively (never passed as an argument or printed).
"""

import argparse
import getpass
import sys
import uuid
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.core.errors import APIError
from app.core.security import normalize_email
from app.db.models.document import Document
from app.db.models.enums import UserRole
from app.db.models.user import User
from app.db.session import SessionLocal
from app.services import auth as auth_service
from app.services import documents as documents_service
from app.services.vector_store import build_vector_store

MIN_PASSWORD_LENGTH = 12


def create_admin(email: str, password: str) -> None:
    """Create an administrator account. Raises APIError if the email already exists."""
    with SessionLocal() as db:
        auth_service.create_user(db, email=email, password=password, role=UserRole.admin)
        db.commit()


def _cmd_create_admin(email: str) -> int:
    password = getpass.getpass(f"Admin password (min {MIN_PASSWORD_LENGTH} chars): ")
    if len(password) < MIN_PASSWORD_LENGTH:
        print(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.", file=sys.stderr)
        return 1
    if password != getpass.getpass("Confirm password: "):
        print("Passwords do not match.", file=sys.stderr)
        return 1
    try:
        create_admin(email, password)
    except APIError as exc:
        print(f"Error: {exc.message}", file=sys.stderr)
        return 1
    print(f"Administrator created: {normalize_email(email)}")
    return 0


def _cmd_ensure_qdrant_collection() -> int:
    settings = get_settings()
    store = build_vector_store(settings)
    store.ensure_collection(settings.embedding_dimensions)
    print(
        f"Qdrant collection '{settings.qdrant_collection}' ready "
        f"({settings.embedding_dimensions} dims, cosine)."
    )
    return 0


def _cmd_reindex(document_id: str) -> int:
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        print("Invalid document id.", file=sys.stderr)
        return 1
    with SessionLocal() as db:
        document = db.get(Document, doc_uuid)
        if document is None:
            print("Document not found.", file=sys.stderr)
            return 1
        try:
            job = documents_service.create_reindex_job(db, document)
        except APIError as exc:
            print(f"Error: {exc.message}", file=sys.stderr)
            return 1
    print(f"Queued reindex job {job.id} for document {doc_uuid}. Ensure the worker is running.")
    return 0


def _resolve_admin(db, email: str | None) -> User:
    """Return the admin user to attribute authored data to."""
    if email is not None:
        user = db.scalar(select(User).where(User.email == normalize_email(email)))
        if user is None:
            raise APIError(404, "not_found", f"No user with email {email}.")
        if user.role != UserRole.admin:
            raise APIError(403, "forbidden", f"{email} is not an administrator.")
        return user
    user = db.scalar(
        select(User).where(User.role == UserRole.admin).order_by(User.created_at).limit(1)
    )
    if user is None:
        raise APIError(404, "not_found", "No administrator account exists. Run create-admin first.")
    return user


def import_benchmark(
    file: str, name: str, description: str | None, replace: bool, email: str | None
) -> uuid.UUID:
    """Import a JSONL question bank into a new draft benchmark version. Returns the version id."""
    from app.services import benchmark as bench

    text = Path(file).read_text(encoding="utf-8")
    with SessionLocal() as db:
        admin = _resolve_admin(db, email)
        cases = bench.parse_jsonl(text)
        version = bench.create_version(db, admin, name, description)
        result = bench.import_cases(db, admin, version, cases, replace)
        version_id = version.id
        print(
            f"Imported {result.imported} cases ({result.judgments} judgments) into "
            f"'{name}' v{version.version} [{version_id}]."
        )
    return version_id


def export_benchmark(version_id: str, out: str | None) -> None:
    """Export a benchmark version to JSONL, to a file or stdout."""
    from app.services import benchmark as bench

    with SessionLocal() as db:
        version = bench.get_version(db, uuid.UUID(version_id))
        jsonl = bench.export_jsonl(db, version)
    if out is None:
        sys.stdout.write(jsonl)
    else:
        Path(out).write_text(jsonl, encoding="utf-8")
        print(f"Exported {jsonl.count(chr(10))} cases to {out}.")


def run_eval(
    benchmark_version_id: str, mode: str, top_k: int, email: str | None
) -> uuid.UUID:
    """Create and synchronously execute an evaluation run. Returns the run id."""
    from app.evals import runner
    from app.retrieval.reranker import build_reranker
    from app.schemas.evals import EvalRunCreate
    from app.services.embeddings import build_embedder

    settings = get_settings()
    embedder = build_embedder(settings)
    vector_store = build_vector_store(settings)
    vector_store.ensure_collection(settings.embedding_dimensions)
    reranker = build_reranker(settings)

    with SessionLocal() as db:
        admin = _resolve_admin(db, email)
        payload = EvalRunCreate(
            benchmark_version_id=uuid.UUID(benchmark_version_id),
            retrieval_mode=mode,
            top_k=top_k,
        )
        run = runner.create_run(db, settings, admin, payload)
        run_id = run.id
        runner.execute_run(db, settings, run, embedder, vector_store, reranker)
        db.refresh(run)
        metrics = run.metrics or {}
    print(f"Eval run {run_id} finished with status '{run.status.value}'.")
    for key in ("hit_at_5", "recall_at_5", "mrr_at_10", "ndcg_at_10", "p95_latency_ms"):
        if key in metrics:
            print(f"  {key}: {metrics[key]}")
    return run_id


def _cmd_import_benchmark(args) -> int:
    try:
        import_benchmark(args.file, args.name, args.description, args.replace, args.email)
    except APIError as exc:
        print(f"Error: {exc.message}", file=sys.stderr)
        return 1
    return 0


def _cmd_export_benchmark(args) -> int:
    try:
        export_benchmark(args.version_id, args.out)
    except APIError as exc:
        print(f"Error: {exc.message}", file=sys.stderr)
        return 1
    return 0


def _cmd_eval_run(args) -> int:
    try:
        run_eval(args.benchmark_version_id, args.mode, args.top_k, args.email)
    except APIError as exc:
        print(f"Error: {exc.message}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_admin_parser = subparsers.add_parser(
        "create-admin", help="Create an administrator account"
    )
    create_admin_parser.add_argument("--email", required=True)

    subparsers.add_parser("ensure-qdrant-collection", help="Create/verify the Qdrant collection")

    reindex_parser = subparsers.add_parser("reindex", help="Queue a document reindex job")
    reindex_parser.add_argument("--document-id", required=True)

    import_parser = subparsers.add_parser(
        "import-benchmark", help="Import a JSONL question bank into a new draft benchmark version"
    )
    import_parser.add_argument("--file", required=True)
    import_parser.add_argument("--name", required=True)
    import_parser.add_argument("--description", default=None)
    import_parser.add_argument("--replace", action="store_true")
    import_parser.add_argument("--email", default=None, help="Admin to attribute (default: first)")

    export_parser = subparsers.add_parser(
        "export-benchmark", help="Export a benchmark version to JSONL"
    )
    export_parser.add_argument("--version-id", required=True)
    export_parser.add_argument("--out", default=None, help="Output file (default: stdout)")

    eval_parser = subparsers.add_parser(
        "eval-run", help="Create and synchronously execute an evaluation run"
    )
    eval_parser.add_argument("--benchmark-version-id", required=True)
    eval_parser.add_argument("--mode", default="hybrid")
    eval_parser.add_argument("--top-k", type=int, default=10)
    eval_parser.add_argument("--email", default=None, help="Admin to attribute (default: first)")

    args = parser.parse_args(argv)
    if args.command == "create-admin":
        return _cmd_create_admin(args.email)
    if args.command == "ensure-qdrant-collection":
        return _cmd_ensure_qdrant_collection()
    if args.command == "reindex":
        return _cmd_reindex(args.document_id)
    if args.command == "import-benchmark":
        return _cmd_import_benchmark(args)
    if args.command == "export-benchmark":
        return _cmd_export_benchmark(args)
    if args.command == "eval-run":
        return _cmd_eval_run(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
