"""Create the first admin account, or promote an existing account to admin.

Usage (from the backend directory, or inside the backend container):
    python scripts/create_admin.py --email admin@example.com --name "Admin"

The password is prompted for unless --password is given.
"""

import argparse
import getpass
import sys
from pathlib import Path

# Make the app package importable when run as a plain script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import ValidationError  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.enums import AccountStatus, UserRole  # noqa: E402
from app.models.user import User  # noqa: E402
from app.schemas.auth import RegisterRequest  # noqa: E402


def create_admin(db: Session, email: str, name: str, password: str) -> tuple[User, bool]:
    """Return (user, created). An existing account keeps its password and is promoted and activated."""
    # Reuse the register rules so admins get the same email and password checks as traders.
    request = RegisterRequest(email=email, password=password, display_name=name)

    user = db.scalar(select(User).where(User.email == request.email))
    created = user is None
    if created:
        user = User(
            email=request.email,
            password_hash=hash_password(request.password),
            display_name=request.display_name,
        )
        db.add(user)
    user.role = UserRole.ADMIN
    user.account_status = AccountStatus.ACTIVE
    db.commit()
    db.refresh(user)
    return user, created


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="Admin", help="display name (default: Admin)")
    parser.add_argument("--password", help="omit to be prompted")
    args = parser.parse_args(argv)

    password = args.password or getpass.getpass("Password (8+ characters): ")

    with SessionLocal() as db:
        try:
            user, created = create_admin(db, args.email, args.name, password)
        except ValidationError as exc:
            for error in exc.errors():
                print(f"error: {error['msg']}", file=sys.stderr)
            return 1

    print(f"{'Created' if created else 'Promoted'} admin {user.email} ({user.user_id})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
