import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("NID_ENCRYPTION_KEY", "00" * 32)
os.environ.setdefault("NID_HASH_KEY", "test-nid-hash-key")
os.environ.setdefault("INTERNAL_CRON_SECRET", "test-cron-secret")
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/tourdesk_test",
    ),
)
os.environ["DATABASE_URL_UNPOOLED"] = os.environ["DATABASE_URL"]
os.environ.pop("DATABASE_URL_DIRECT", None)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

import app.models
from app.core.db import Base, dispose_engine, get_engine
from app.core.rate_limit import reset_rate_limits
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def prepare_schema():
    engine = get_engine()
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
        Base.metadata.drop_all(bind=connection)
        Base.metadata.create_all(bind=connection)
    yield
    dispose_engine()


@pytest.fixture(autouse=True)
def clean_db(prepare_schema):
    engine = get_engine()
    tables = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))
    reset_rate_limits()
    yield


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def two_operators():
    """Cross-tenant fixture: two approved operators (A and B) with owner tokens + an admin token."""
    import uuid

    from app.core.db import get_session_factory
    from app.core.security import create_access_token, hash_password, utcnow
    from app.modules.operators.models import Operator, OperatorMember
    from app.modules.users.models import User

    with get_session_factory()() as db:
        admin = User(
            id=uuid.uuid4(),
            full_name="Platform Admin",
            email="admin-fixture@example.com",
            phone="+8801700000000",
            password_hash=hash_password("Pass1234!"),
            role="ADMIN",
            status="ACTIVE",
            consented_at=utcnow(),
        )
        user_a = User(
            id=uuid.uuid4(),
            full_name="Owner A",
            email="ownera@example.com",
            phone="+8801700000001",
            password_hash=hash_password("Pass1234!"),
            role="OPERATOR",
            status="ACTIVE",
            consented_at=utcnow(),
        )
        user_b = User(
            id=uuid.uuid4(),
            full_name="Owner B",
            email="ownerb@example.com",
            phone="+8801700000002",
            password_hash=hash_password("Pass1234!"),
            role="OPERATOR",
            status="ACTIVE",
            consented_at=utcnow(),
        )
        db.add_all([admin, user_a, user_b])
        db.flush()

        op_a = Operator(
            id=uuid.uuid4(),
            kind="TOUR",
            type="GROUP",
            display_name="Sajek Explorers",
            contact_phone="+8801800000001",
            payout_methods=[{"provider": "BKASH", "number": "01800000001"}],
            verification_status="APPROVED",
            verified_by=admin.id,
            verified_at=utcnow(),
        )
        op_b = Operator(
            id=uuid.uuid4(),
            kind="TOUR",
            type="INDIVIDUAL",
            display_name="Sylhet Trails",
            contact_phone="+8801800000002",
            payout_methods=[{"provider": "NAGAD", "number": "01800000002"}],
            verification_status="APPROVED",
            verified_by=admin.id,
            verified_at=utcnow(),
        )
        db.add_all([op_a, op_b])
        db.flush()

        db.add_all(
            [
                OperatorMember(operator_id=op_a.id, user_id=user_a.id, member_role="OWNER"),
                OperatorMember(operator_id=op_b.id, user_id=user_b.id, member_role="OWNER"),
            ]
        )
        db.commit()

        token_a, _ = create_access_token(user_a.id, "OPERATOR")
        token_b, _ = create_access_token(user_b.id, "OPERATOR")
        token_admin, _ = create_access_token(admin.id, "ADMIN")
        return {
            "admin_id": admin.id,
            "admin_token": token_admin,
            "op_a_id": op_a.id,
            "user_a_id": user_a.id,
            "token_a": token_a,
            "op_b_id": op_b.id,
            "user_b_id": user_b.id,
            "token_b": token_b,
        }
