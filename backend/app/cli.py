"""Command-line administration for CircuitSage.

Usage:
    python -m app.cli create-admin --email admin@example.com

The password is read interactively (never passed as an argument or printed).
"""

import argparse
import getpass
import sys

from app.core.errors import APIError
from app.core.security import normalize_email
from app.db.models.enums import UserRole
from app.db.session import SessionLocal
from app.services import auth as auth_service

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_admin_parser = subparsers.add_parser(
        "create-admin", help="Create an administrator account"
    )
    create_admin_parser.add_argument("--email", required=True)

    args = parser.parse_args(argv)
    if args.command == "create-admin":
        return _cmd_create_admin(args.email)
    return 2


if __name__ == "__main__":
    sys.exit(main())
