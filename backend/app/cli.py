"""Operator CLI: admin seeding and reconciliation helpers.

Usage:
    python -m app.cli create-admin --email a@b.com --password secret \
        --full-name Admin --phone +8801712345678
"""

import argparse
import sys

from sqlalchemy import select

from app.core.db import get_session_factory
from app.core.security import hash_password, utcnow
from app.jobs.sweeper import reconcile_departure_seats
from app.modules.users.models import User
from app.seed import seed_demo_data


def seed_demo(_: argparse.Namespace) -> int:
    with get_session_factory()() as db:
        seed_demo_data(db)
        print("Demo data seeded.")
        return 0


def reconcile_seats(args: argparse.Namespace) -> int:
    with get_session_factory()() as db:
        drifts = reconcile_departure_seats(db, fix=args.fix)
        if not drifts:
            print("All departure seat counts match active bookings.")
            return 0
        for d in drifts:
            print(
                f"DRIFT departure={d['departure_id']} recorded={d['recorded']} actual={d['actual']}"
            )
        return 0 if args.fix else 1


def create_admin(args: argparse.Namespace) -> int:
    with get_session_factory()() as db:
        existing = db.scalar(select(User).where(User.email == args.email.lower()))
        if existing is not None:
            print("A user with this email already exists", file=sys.stderr)
            return 1
        user = User(
            full_name=args.full_name,
            email=args.email.lower(),
            phone=args.phone,
            password_hash=hash_password(args.password),
            role="ADMIN",
            status="ACTIVE",
            consented_at=utcnow(),
        )
        db.add(user)
        db.commit()
        print(f"Admin created: {user.email} ({user.id})")
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    admin = sub.add_parser("create-admin", help="Create a platform admin account")
    admin.add_argument("--email", required=True)
    admin.add_argument("--password", required=True)
    admin.add_argument("--full-name", required=True)
    admin.add_argument("--phone", required=True)
    admin.set_defaults(func=create_admin)

    rec = sub.add_parser("reconcile-seats", help="Check/fix departure seat count drift")
    rec.add_argument("--fix", action="store_true", help="Repair drifted counts")
    rec.set_defaults(func=reconcile_seats)

    seed = sub.add_parser("seed-demo", help="Seed realistic Bangladesh demo data")
    seed.set_defaults(func=seed_demo)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
