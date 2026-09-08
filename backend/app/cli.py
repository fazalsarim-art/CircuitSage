"""Command-line administration for CircuitSage.

Usage:
    python -m app.cli create-admin --email admin@example.com

The password is read interactively (never passed as an argument or printed).
"""

import argparse
import getpass
import sys
import uuid

from app.core.config import get_settings
from app.core.errors import APIError
from app.core.security import normalize_email
from app.db.models.document import Document
from app.db.models.enums import UserRole
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

    args = parser.parse_args(argv)
    if args.command == "create-admin":
        return _cmd_create_admin(args.email)
    if args.command == "ensure-qdrant-collection":
        return _cmd_ensure_qdrant_collection()
    if args.command == "reindex":
        return _cmd_reindex(args.document_id)
    return 2


if __name__ == "__main__":
    sys.exit(main())
