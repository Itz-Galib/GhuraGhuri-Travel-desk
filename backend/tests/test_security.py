"""Security threat checklist tests (spec 05 & T6.1)."""

import uuid
from datetime import date

from fastapi.testclient import TestClient

from app.core.db import get_session_factory
from app.modules.tours.models import Departure, TourPackage


def test_suspended_operator_hidden_from_public_catalog(
    client: TestClient, two_operators: dict
) -> None:
    with get_session_factory()() as db:
        pkg = TourPackage(
            id=uuid.uuid4(),
            operator_id=two_operators["op_a_id"],
            title="Coxs Bazar Weekend",
            slug="coxs-bazar-weekend",
            destination="Cox's Bazar",
            summary="Marine drive and Inani beach.",
            description="2-day beach getaway.",
            duration_days=2,
            base_price=500000,
            advance_percent=30,
            cancellation_policy="Flexible",
            status="PUBLISHED",
        )
        db.add(pkg)
        db.flush()
        db.add(
            Departure(
                id=uuid.uuid4(),
                package_id=pkg.id,
                start_date=date(2026, 12, 26),
                end_date=date(2026, 12, 27),
                price=500000,
                capacity=10,
                status="OPEN",
            )
        )
        db.commit()

    # Visible initially
    assert client.get("/api/v1/tours/coxs-bazar-weekend").status_code == 200

    # Admin suspends operator A -> immediately hidden from public search & detail
    susp = client.post(
        f"/api/v1/admin/operators/{two_operators['op_a_id']}/suspend",
        headers={"Authorization": f"Bearer {two_operators['admin_token']}"},
        json={"reason": "Fraud report"},
    )
    assert susp.status_code == 200
    assert client.get("/api/v1/tours/coxs-bazar-weekend").status_code == 404
    assert client.get("/api/v1/tours").json()["total"] == 0


def test_forged_operator_approval_and_cron_secret_blocked(
    client: TestClient, two_operators: dict
) -> None:
    # Operator A cannot approve Operator B or access admin endpoints
    hdr_a = {"Authorization": f"Bearer {two_operators['token_a']}"}
    assert (
        client.post(
            f"/api/v1/admin/operators/{two_operators['op_b_id']}/approve",
            headers=hdr_a,
            json={"reason": "Self approve"},
        ).status_code
        == 403
    )

    # Internal cron sweep requires valid X-Cron-Secret
    assert client.post("/api/v1/internal/cron/sweep").status_code == 403
    assert (
        client.post(
            "/api/v1/internal/cron/sweep",
            headers={"X-Cron-Secret": "wrong-secret"},
        ).status_code
        == 403
    )
    ok = client.post(
        "/api/v1/internal/cron/sweep",
        headers={"X-Cron-Secret": "test-cron-secret"},
    )
    assert ok.status_code == 200
    assert ok.json() == {"expired": 0}
