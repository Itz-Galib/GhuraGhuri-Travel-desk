"""Auth & RBAC tests (T1.1, T1.2, T1.3)."""

import sys
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.cli import main as cli_main
from app.core.db import get_session_factory
from app.core.security import hash_password, utcnow
from app.modules.users.models import RefreshToken, User

VALID_USER = {
    "full_name": "Rafiqul Islam",
    "email": "rafiq@example.com",
    "phone": "+8801712345678",
    "password": "StrongPassword123!",
    "consent": True,
}


def test_register_login_me_and_update(client: TestClient) -> None:
    res = client.post("/api/v1/auth/register", json=VALID_USER)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["access_token"]
    assert body["user"]["role"] == "CUSTOMER"
    assert body["user"]["email"] == "rafiq@example.com"
    assert "refresh_token" in res.cookies

    token = body["access_token"]
    me_res = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["user"]["phone"] == "+8801712345678"
    assert me_res.json()["operator_memberships"] == []

    patch_res = client.patch(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"full_name": "Rafiq Updated"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["user"]["full_name"] == "Rafiq Updated"


def test_register_validation_failures(client: TestClient) -> None:
    # Bad phone
    bad_phone = {**VALID_USER, "phone": "01712345678"}
    assert client.post("/api/v1/auth/register", json=bad_phone).status_code == 400

    # Common password
    bad_pw = {**VALID_USER, "password": "password123"}
    assert client.post("/api/v1/auth/register", json=bad_pw).status_code == 400

    # Missing consent
    no_consent = {**VALID_USER, "consent": False}
    assert client.post("/api/v1/auth/register", json=no_consent).status_code == 400


def test_privilege_escalation_on_register_ignored(client: TestClient) -> None:
    payload = {**VALID_USER, "role": "ADMIN", "status": "SUSPENDED"}
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201
    assert res.json()["user"]["role"] == "CUSTOMER"
    assert res.json()["user"]["status"] == "ACTIVE"


def test_refresh_rotation_and_reuse_revocation(client: TestClient) -> None:
    res = client.post("/api/v1/auth/register", json=VALID_USER)
    assert res.status_code == 201
    old_cookie = res.cookies["refresh_token"]

    # Missing CSRF header -> 403
    no_hdr = client.post("/api/v1/auth/refresh", cookies={"refresh_token": old_cookie})
    assert no_hdr.status_code == 403

    # Valid refresh rotates token
    rot = client.post(
        "/api/v1/auth/refresh",
        headers={"X-Requested-With": "XMLHttpRequest"},
        cookies={"refresh_token": old_cookie},
    )
    assert rot.status_code == 200
    new_cookie = rot.cookies["refresh_token"]
    assert new_cookie != old_cookie

    # Reuse of rotated token revokes entire family
    reuse = client.post(
        "/api/v1/auth/refresh",
        headers={"X-Requested-With": "XMLHttpRequest"},
        cookies={"refresh_token": old_cookie},
    )
    assert reuse.status_code == 401

    # Now even the new cookie is revoked!
    after_revoke = client.post(
        "/api/v1/auth/refresh",
        headers={"X-Requested-With": "XMLHttpRequest"},
        cookies={"refresh_token": new_cookie},
    )
    assert after_revoke.status_code == 401


def test_logout_revokes_family(client: TestClient) -> None:
    res = client.post("/api/v1/auth/register", json=VALID_USER)
    cookie = res.cookies["refresh_token"]

    out = client.post("/api/v1/auth/logout", cookies={"refresh_token": cookie})
    assert out.status_code == 204

    again = client.post(
        "/api/v1/auth/refresh",
        headers={"X-Requested-With": "XMLHttpRequest"},
        cookies={"refresh_token": cookie},
    )
    assert again.status_code == 401


def test_login_lockout_after_five_failures(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=VALID_USER)
    for _ in range(5):
        r = client.post(
            "/api/v1/auth/login",
            json={"identifier": VALID_USER["email"], "password": "wrong-password"},
        )
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"

    locked = client.post(
        "/api/v1/auth/login",
        json={"identifier": VALID_USER["email"], "password": VALID_USER["password"]},
    )
    assert locked.status_code == 429


def test_login_unknown_user_same_error(client: TestClient) -> None:
    r = client.post(
        "/api/v1/auth/login",
        json={"identifier": "nobody@example.com", "password": "wrong-password"},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_cli_create_admin(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "app.cli",
            "create-admin",
            "--email",
            "admin@ghuraghuri.com",
            "--password",
            "AdminPass123!",
            "--full-name",
            "Platform Admin",
            "--phone",
            "+8801812345678",
        ],
    )
    assert cli_main() == 0
    with get_session_factory()() as db:  # type: Session
        admin = db.scalar(select(User).where(User.email == "admin@ghuraghuri.com"))
        assert admin is not None
        assert admin.role == "ADMIN"

    # Duplicate email returns 1
    assert cli_main() == 1


def test_rbac_dependencies_deny_unauthorised_roles() -> None:
    from fastapi import Depends, FastAPI

    from app.core.deps import get_admin_user, require_role
    from app.core.errors import AppError, app_error_handler

    probe = FastAPI()
    probe.add_exception_handler(AppError, app_error_handler)

    @probe.get("/only-admin")
    def only_admin(user: User = Depends(get_admin_user)) -> dict[str, str]:
        return {"id": str(user.id)}

    @probe.get("/only-operator")
    def only_operator(user: User = Depends(require_role("OPERATOR"))) -> dict[str, str]:
        return {"id": str(user.id)}

    with get_session_factory()() as db:
        customer = User(
            id=uuid.uuid4(),
            full_name="Cust",
            email="cust@example.com",
            phone="+8801911111111",
            password_hash=hash_password("Pass1234!"),
            role="CUSTOMER",
            status="ACTIVE",
            consented_at=utcnow(),
        )
        db.add(customer)
        db.commit()

    from app.core.security import create_access_token

    token, _ = create_access_token(customer.id, "CUSTOMER")
    probe_client = TestClient(probe)
    assert probe_client.get("/only-admin").status_code == 401
    assert (
        probe_client.get("/only-admin", headers={"Authorization": f"Bearer {token}"}).status_code
        == 403
    )
    assert (
        probe_client.get("/only-operator", headers={"Authorization": f"Bearer {token}"}).status_code
        == 403
    )
    # Silence unused import warning for RefreshToken
    assert RefreshToken.__tablename__ == "refresh_tokens"
