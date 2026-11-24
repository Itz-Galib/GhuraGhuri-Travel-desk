"""Operator onboarding, NID crypto, admin review, and cross-tenant tests (T2.2, T2.3, T2.5)."""

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.crypto import decrypt_nid, encrypt_nid, hash_nid, nid_last4
from app.core.db import get_session_factory
from app.modules.audit.models import AuditLog

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _register_user(client: TestClient, email: str, phone: str) -> str:
    res = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Test Operator",
            "email": email,
            "phone": phone,
            "password": "StrongPassword123!",
            "consent": True,
        },
    )
    assert res.status_code == 201
    return str(res.json()["access_token"])


def test_nid_encryption_and_hashing() -> None:
    raw = "1234567890"
    blob = encrypt_nid(raw)
    assert blob != raw.encode()
    assert decrypt_nid(blob) == raw
    assert nid_last4(raw) == "7890"
    assert hash_nid(raw) == hash_nid("1234-5678-90")


def test_operator_onboarding_and_admin_review(client: TestClient, two_operators: dict) -> None:
    token = _register_user(client, "newop@example.com", "+8801711112222")

    # 1. Create profile
    prof = client.post(
        "/api/v1/operator/profile",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "type": "GROUP",
            "display_name": "Sundarban Voyagers",
            "contact_phone": "+8801711112222",
            "facebook_url": "https://facebook.com/groups/sundarban",
            "payout_methods": [{"provider": "BKASH", "number": "01711112222"}],
        },
    )
    assert prof.status_code == 201, prof.text
    op_id = prof.json()["id"]
    assert prof.json()["verification_status"] == "DRAFT"

    # 2. Invalid file magic bytes rejected
    bad_file = client.post(
        "/api/v1/operator/documents",
        headers={"Authorization": f"Bearer {token}"},
        data={"person_name": "Karim", "doc_type": "NID_FRONT", "nid_number": "1234567890"},
        files={"file": ("fake.png", b"not-a-png", "image/png")},
    )
    assert bad_file.status_code == 400

    # 3. Valid NID_FRONT upload
    doc = client.post(
        "/api/v1/operator/documents",
        headers={"Authorization": f"Bearer {token}"},
        data={"person_name": "Karim", "doc_type": "NID_FRONT", "nid_number": "1234567890"},
        files={"file": ("nid.png", PNG_BYTES, "image/png")},
    )
    assert doc.status_code == 201, doc.text
    doc_id = doc.json()["id"]
    assert doc.json()["nid_last4"] == "7890"
    assert "nid_number" not in doc.json()
    assert "nid_encrypted" not in doc.json()

    # 4. Duplicate NID blocked for another operator
    token2 = _register_user(client, "dup@example.com", "+8801711113333")
    client.post(
        "/api/v1/operator/profile",
        headers={"Authorization": f"Bearer {token2}"},
        json={
            "type": "INDIVIDUAL",
            "display_name": "Dup Op",
            "contact_phone": "+8801711113333",
            "payout_methods": [{"provider": "NAGAD", "number": "01711113333"}],
        },
    )
    dup_doc = client.post(
        "/api/v1/operator/documents",
        headers={"Authorization": f"Bearer {token2}"},
        data={"person_name": "Fake", "doc_type": "NID_FRONT", "nid_number": "1234567890"},
        files={"file": ("nid.png", PNG_BYTES, "image/png")},
    )
    assert dup_doc.status_code == 409

    # 5. Submit for verification
    sub = client.post(
        "/api/v1/operator/submit",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert sub.status_code == 200
    assert sub.json()["verification_status"] == "PENDING"

    # 6. Non-admin cannot view admin endpoints
    assert (
        client.get(
            "/api/v1/admin/operators",
            headers={"Authorization": f"Bearer {token}"},
        ).status_code
        == 403
    )

    # 7. Admin views detail, gets signed URL (audit logged), approves
    admin_hdr = {"Authorization": f"Bearer {two_operators['admin_token']}"}
    detail = client.get(f"/api/v1/admin/operators/{op_id}", headers=admin_hdr)
    assert detail.status_code == 200
    assert len(detail.json()["documents"]) == 1

    signed = client.get(
        f"/api/v1/admin/operators/{op_id}/documents/{doc_id}/url",
        headers=admin_hdr,
    )
    assert signed.status_code == 200
    signed_url = signed.json()["url"]
    assert client.get(signed_url).status_code == 200

    approved = client.post(
        f"/api/v1/admin/operators/{op_id}/approve",
        headers=admin_hdr,
        json={"reason": "Verified NID and payout"},
    )
    assert approved.status_code == 200
    assert approved.json()["verification_status"] == "APPROVED"

    with get_session_factory()() as db:
        actions = list(db.scalars(select(AuditLog.action)))
        assert "NID_VIEWED" in actions
        assert "OPERATOR_APPROVED" in actions


def test_operator_member_invite_and_staff_restriction(
    client: TestClient, two_operators: dict
) -> None:
    staff_token = _register_user(client, "staff@example.com", "+8801755556666")
    invite = client.post(
        "/api/v1/operator/members",
        headers={"Authorization": f"Bearer {two_operators['token_a']}"},
        json={"identifier": "staff@example.com"},
    )
    assert invite.status_code == 201
    assert invite.json()["member_role"] == "STAFF"

    # Staff cannot list or invite members (OWNER only)
    assert (
        client.get(
            "/api/v1/operator/members",
            headers={"Authorization": f"Bearer {staff_token}"},
        ).status_code
        == 403
    )
