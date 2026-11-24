"""Admin manual booking, notify-unavailable, CSV export, offers, dashboards tests (T5.1-T5.4)."""

import uuid
from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.core.db import get_session_factory
from app.core.security import utcnow
from app.modules.tours.models import Departure, TourPackage


def test_admin_manual_booking_notify_unavailable_csv_and_dashboard(
    client: TestClient, two_operators: dict
) -> None:
    with get_session_factory()() as db:
        pkg = TourPackage(
            id=uuid.uuid4(),
            operator_id=two_operators["op_a_id"],
            title="Sylhet Tea Trails",
            slug="sylhet-tea-trails",
            destination="Sylhet",
            summary="Tea gardens and Ratargul.",
            description="2-day guided tour in Sylhet.",
            duration_days=2,
            base_price=450000,
            advance_percent=30,
            cancellation_policy="Flexible",
            status="PUBLISHED",
        )
        db.add(pkg)
        db.flush()
        dep = Departure(
            id=uuid.uuid4(),
            package_id=pkg.id,
            start_date=date(2026, 12, 26),
            end_date=date(2026, 12, 27),
            price=450000,
            capacity=15,
            status="OPEN",
        )
        db.add(dep)
        db.commit()
        pkg_id, dep_id = pkg.id, dep.id

    hdr_admin = {"Authorization": f"Bearer {two_operators['admin_token']}"}
    hdr_a = {"Authorization": f"Bearer {two_operators['token_a']}"}

    # 1. Admin creates manual Facebook booking with advance paid -> CONFIRMED
    manual = client.post(
        "/api/v1/admin/bookings",
        headers=hdr_admin,
        json={
            "departure_id": str(dep_id),
            "seats": 2,
            "contact_name": "FB Customer",
            "contact_phone": "+8801812345678",
            "source": "FACEBOOK",
            "advance_paid_amount": 300000,
            "payment_provider": "BKASH",
            "provider_txn_id": "FB-TRX-1",
            "needs_attention": True,
        },
    )
    assert manual.status_code == 201, manual.text
    booking_id = manual.json()["id"]
    assert manual.json()["status"] == "CONFIRMED"
    assert manual.json()["source"] == "FACEBOOK"

    # 2. CSV export
    csv_res = client.get("/api/v1/admin/bookings?format=csv", headers=hdr_admin)
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers["content-type"]
    assert "FB Customer" in csv_res.text

    # 3. Notify unavailable -> CANCELLED_UNAVAILABLE + releases seats + WhatsApp URL
    unavail = client.post(
        f"/api/v1/admin/bookings/{booking_id}/notify-unavailable",
        headers=hdr_admin,
        json={"reason": "Boat maintenance"},
    )
    assert unavail.status_code == 200, unavail.text
    assert unavail.json()["status"] == "CANCELLED_UNAVAILABLE"
    assert "https://wa.me/8801812345678" in unavail.json()["whatsapp_url"]

    # 4. Admin offers CRUD & tour suspend/unsuspend
    now = utcnow()
    offer = client.post(
        "/api/v1/admin/offers",
        headers=hdr_admin,
        json={
            "package_id": str(pkg_id),
            "title": "Holiday Deal",
            "discount_type": "FLAT",
            "discount_value": 50000,
            "starts_at": (now - timedelta(days=1)).isoformat(),
            "ends_at": (now + timedelta(days=5)).isoformat(),
        },
    )
    assert offer.status_code == 201

    susp = client.post(
        f"/api/v1/admin/tours/{pkg_id}/suspend",
        headers=hdr_admin,
        json={"reason": "Verification check"},
    )
    assert susp.status_code == 200
    assert susp.json()["status"] == "SUSPENDED"

    # 5. Dashboards & audit logs
    admin_dash = client.get("/api/v1/admin/dashboard", headers=hdr_admin)
    assert admin_dash.status_code == 200
    assert admin_dash.json()["revenue_booked"] == 300000

    op_dash = client.get("/api/v1/operator/dashboard", headers=hdr_a)
    assert op_dash.status_code == 200
    assert op_dash.json()["packages_count"] == 1

    audits = client.get("/api/v1/admin/audit-logs", headers=hdr_admin)
    assert audits.status_code == 200
    assert audits.json()["total"] >= 3
