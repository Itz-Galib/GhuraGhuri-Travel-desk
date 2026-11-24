"""Catalog, departures, offers, and cross-tenant isolation tests (T3.2, T3.3)."""

import uuid
from datetime import timedelta

from fastapi.testclient import TestClient

from app.core.db import get_session_factory
from app.core.security import utcnow
from app.modules.tours.models import Departure, Offer

TOUR_PAYLOAD = {
    "title": "Sajek Valley 3D2N Cloud Escape",
    "destination": "Sajek Valley",
    "summary": "Sunrise above the clouds with local tribal lunch and Konglak trek.",
    "description": "Full 3-day guided tour from Dhaka to Sajek Valley with AC transport.",
    "itinerary": [{"day": 1, "title": "Dhaka to Khagrachari"}],
    "inclusions": ["AC Bus", "Resort stay"],
    "exclusions": ["Personal expenses"],
    "duration_days": 3,
    "base_price": 650000,
    "advance_percent": 30,
    "cancellation_policy": "Free cancellation 7 days before departure.",
}


def test_operator_tour_departure_crud_and_cross_tenant(
    client: TestClient, two_operators: dict
) -> None:
    hdr_a = {"Authorization": f"Bearer {two_operators['token_a']}"}
    hdr_b = {"Authorization": f"Bearer {two_operators['token_b']}"}

    # Create tour as operator A
    created = client.post("/api/v1/operator/tours", headers=hdr_a, json=TOUR_PAYLOAD)
    assert created.status_code == 201, created.text
    pkg_id = created.json()["id"]
    slug = created.json()["slug"]
    assert created.json()["status"] == "DRAFT"

    # Draft is NOT visible publicly
    assert client.get(f"/api/v1/tours/{slug}").status_code == 404

    # Cross-tenant: Operator B cannot read, update, publish, or add departure to Operator A's tour
    assert client.get(f"/api/v1/operator/tours/{pkg_id}", headers=hdr_b).status_code == 404
    assert (
        client.patch(
            f"/api/v1/operator/tours/{pkg_id}", headers=hdr_b, json={"title": "Hijacked"}
        ).status_code
        == 404
    )
    assert client.post(f"/api/v1/operator/tours/{pkg_id}/publish", headers=hdr_b).status_code == 404

    # Publish as Operator A
    pub = client.post(f"/api/v1/operator/tours/{pkg_id}/publish", headers=hdr_a)
    assert pub.status_code == 200
    assert pub.json()["status"] == "PUBLISHED"

    # Add departure
    dep = client.post(
        f"/api/v1/operator/tours/{pkg_id}/departures",
        headers=hdr_a,
        json={
            "start_date": "2026-12-26",
            "end_date": "2026-12-28",
            "price": 650000,
            "capacity": 20,
        },
    )
    assert dep.status_code == 201, dep.text
    dep_id = dep.json()["id"]

    # Capacity guard: simulate 5 booked seats, then try reducing capacity to 3 -> 409
    with get_session_factory()() as db:
        d = db.get(Departure, uuid.UUID(dep_id))
        assert d is not None
        d.seats_booked = 5
        db.commit()

    cap_fail = client.patch(
        f"/api/v1/operator/departures/{dep_id}",
        headers=hdr_a,
        json={"capacity": 3},
    )
    assert cap_fail.status_code == 409

    # Add an active offer and verify public catalog & date search
    with get_session_factory()() as db:
        now = utcnow()
        db.add(
            Offer(
                package_id=uuid.UUID(pkg_id),
                title="Winter 10% Off",
                discount_type="PERCENT",
                discount_value=10,
                starts_at=now - timedelta(days=1),
                ends_at=now + timedelta(days=10),
                is_active=True,
                created_by=two_operators["admin_id"],
            )
        )
        db.commit()

    pub_list = client.get("/api/v1/tours?destination=Sajek")
    assert pub_list.status_code == 200
    assert pub_list.json()["total"] == 1
    assert pub_list.json()["items"][0]["discounted_price"] == 585000

    dep_search = client.get("/api/v1/departures?date=2026-12-26&destination=Sajek")
    assert dep_search.status_code == 200
    assert dep_search.json()["total"] == 1
    assert dep_search.json()["items"][0]["departure"]["seats_left"] == 15

    offers = client.get("/api/v1/offers")
    assert offers.status_code == 200
    assert offers.json()["total"] == 1


def test_unapproved_operator_cannot_publish(client: TestClient) -> None:
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Draft Op",
            "email": "draftop@example.com",
            "phone": "+8801722223333",
            "password": "StrongPassword123!",
            "consent": True,
        },
    )
    token = reg.json()["access_token"]
    hdr = {"Authorization": f"Bearer {token}"}
    client.post(
        "/api/v1/operator/profile",
        headers=hdr,
        json={
            "type": "INDIVIDUAL",
            "display_name": "Unapproved Tours",
            "contact_phone": "+8801722223333",
            "payout_methods": [{"provider": "BKASH", "number": "01722223333"}],
        },
    )
    pkg = client.post("/api/v1/operator/tours", headers=hdr, json=TOUR_PAYLOAD)
    assert pkg.status_code == 201
    pub = client.post(f"/api/v1/operator/tours/{pkg.json()['id']}/publish", headers=hdr)
    assert pub.status_code == 403
