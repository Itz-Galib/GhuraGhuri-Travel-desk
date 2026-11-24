"""Booking state machine, atomic concurrency, idempotency, payments, sweeper tests (T4.2-T4.6)."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.db import get_session_factory
from app.core.errors import ConflictError
from app.core.security import create_access_token, hash_password, utcnow
from app.jobs.sweeper import expire_stale_bookings, reconcile_departure_seats
from app.modules.bookings.models import Booking
from app.modules.bookings.state import ALLOWED_TRANSITIONS, validate_transition
from app.modules.tours.models import Departure, TourPackage
from app.modules.users.models import User


def _seed_departure(operator_id: uuid.UUID, capacity: int = 10) -> tuple[uuid.UUID, str]:
    with get_session_factory()() as db:
        pkg = TourPackage(
            id=uuid.uuid4(),
            operator_id=operator_id,
            title="Sundarbans Cruise",
            slug=f"sundarbans-{uuid.uuid4().hex[:6]}",
            destination="Sundarbans",
            summary="3-day vessel cruise.",
            description="Explore Kotka and Jamtola beach.",
            duration_days=3,
            base_price=1000000,
            advance_percent=30,
            cancellation_policy="Moderate",
            status="PUBLISHED",
        )
        db.add(pkg)
        db.flush()
        dep = Departure(
            id=uuid.uuid4(),
            package_id=pkg.id,
            start_date=date(2026, 12, 26),
            end_date=date(2026, 12, 28),
            price=1000000,
            capacity=capacity,
            status="OPEN",
        )
        db.add(dep)
        cust = User(
            id=uuid.uuid4(),
            full_name="Customer One",
            email=f"cust-{uuid.uuid4().hex[:6]}@example.com",
            phone=f"+88017{uuid.uuid4().int % 100000000:08d}",
            password_hash=hash_password("Pass1234!"),
            role="CUSTOMER",
            status="ACTIVE",
            consented_at=utcnow(),
        )
        db.add(cust)
        db.commit()
        token, _ = create_access_token(cust.id, "CUSTOMER")
        return dep.id, token


def test_booking_state_machine_every_transition() -> None:
    all_states = set(ALLOWED_TRANSITIONS.keys())
    for src, targets in ALLOWED_TRANSITIONS.items():
        for dst in all_states:
            if dst in targets:
                validate_transition(src, dst)
            else:
                with pytest.raises(ConflictError):
                    validate_transition(src, dst)


def test_booking_idempotency_payment_and_cancellation(
    client: TestClient, two_operators: dict
) -> None:
    dep_id, cust_token = _seed_departure(two_operators["op_a_id"], capacity=10)
    hdr_c = {"Authorization": f"Bearer {cust_token}"}
    hdr_a = {"Authorization": f"Bearer {two_operators['token_a']}"}
    hdr_b = {"Authorization": f"Bearer {two_operators['token_b']}"}

    payload = {
        "departure_id": str(dep_id),
        "seats": 2,
        "contact_name": "Customer One",
        "contact_phone": "+8801712345678",
        "travellers": [{"full_name": "Traveller 1"}, {"full_name": "Traveller 2"}],
    }
    idem = str(uuid.uuid4())
    r1 = client.post(
        "/api/v1/bookings",
        headers={**hdr_c, "Idempotency-Key": idem},
        json=payload,
    )
    assert r1.status_code == 201, r1.text
    booking_id = r1.json()["id"]

    # Replay returns exact same booking
    r2 = client.post(
        "/api/v1/bookings",
        headers={**hdr_c, "Idempotency-Key": idem},
        json=payload,
    )
    assert r2.status_code == 201
    assert r2.json()["id"] == booking_id

    # Different body with same key -> 409
    r_diff = client.post(
        "/api/v1/bookings",
        headers={**hdr_c, "Idempotency-Key": idem},
        json={**payload, "seats": 3},
    )
    assert r_diff.status_code == 409

    # Submit payment
    pay = client.post(
        f"/api/v1/bookings/{booking_id}/payments",
        headers=hdr_c,
        json={
            "provider": "BKASH",
            "amount": 600000,
            "sender_number": "+8801712345678",
            "provider_txn_id": "TRX-1001",
        },
    )
    assert pay.status_code == 201, pay.text
    pay_id = pay.json()["id"]

    # Duplicate TrxID rejected
    dup_pay = client.post(
        f"/api/v1/bookings/{booking_id}/payments",
        headers=hdr_c,
        json={
            "provider": "BKASH",
            "amount": 600000,
            "sender_number": "+8801712345678",
            "provider_txn_id": "TRX-1001",
        },
    )
    assert dup_pay.status_code == 409

    # Cross-tenant: Operator B cannot verify Operator A's payment -> 404
    assert (
        client.post(
            f"/api/v1/operator/payments/{pay_id}/verify",
            headers=hdr_b,
            json={"approve": True},
        ).status_code
        == 404
    )

    # Operator A verifies payment -> booking becomes CONFIRMED
    ver = client.post(
        f"/api/v1/operator/payments/{pay_id}/verify",
        headers=hdr_a,
        json={"approve": True},
    )
    assert ver.status_code == 200
    assert ver.json()["status"] == "VERIFIED"

    detail = client.get(f"/api/v1/bookings/{booking_id}", headers=hdr_c)
    assert detail.json()["status"] == "CONFIRMED"

    # Customer requests cancellation -> CANCELLATION_REQUESTED -> Operator approves -> CANCELLED
    creq = client.post(
        f"/api/v1/bookings/{booking_id}/cancel-request",
        headers=hdr_c,
        json={"reason": "Change of plans"},
    )
    assert creq.status_code == 200
    assert creq.json()["status"] == "CANCELLATION_REQUESTED"

    cdec = client.post(
        f"/api/v1/operator/bookings/{booking_id}/cancel-decision",
        headers=hdr_a,
        json={"approve": True, "reason": "Approved"},
    )
    assert cdec.status_code == 200
    assert cdec.json()["status"] == "CANCELLED"

    # Reconciliation invariant 1 passes with zero drift
    with get_session_factory()() as db:
        assert reconcile_departure_seats(db) == []


def test_concurrency_50_parallel_requests_for_5_seats(
    client: TestClient, two_operators: dict
) -> None:
    dep_id, cust_token = _seed_departure(two_operators["op_a_id"], capacity=5)

    def attempt_book(i: int) -> int:
        res = client.post(
            "/api/v1/bookings",
            headers={
                "Authorization": f"Bearer {cust_token}",
                "Idempotency-Key": f"race-{i}-{uuid.uuid4()}",
            },
            json={
                "departure_id": str(dep_id),
                "seats": 1,
                "contact_name": f"User {i}",
                "contact_phone": "+8801712345678",
                "travellers": [{"full_name": f"Traveller {i}"}],
            },
        )
        return res.status_code

    with ThreadPoolExecutor(max_workers=16) as pool:
        statuses = list(pool.map(attempt_book, range(50)))

    assert statuses.count(201) == 5
    assert statuses.count(409) == 45

    with get_session_factory()() as db:
        dep = db.get(Departure, dep_id)
        assert dep is not None
        assert dep.seats_booked == 5
        assert reconcile_departure_seats(db) == []


def test_sweeper_expires_holds_and_bulk_cancel(client: TestClient, two_operators: dict) -> None:
    dep_id, cust_token = _seed_departure(two_operators["op_a_id"], capacity=10)
    hdr_c = {"Authorization": f"Bearer {cust_token}"}
    hdr_a = {"Authorization": f"Bearer {two_operators['token_a']}"}

    r1 = client.post(
        "/api/v1/bookings",
        headers={**hdr_c, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "departure_id": str(dep_id),
            "seats": 3,
            "contact_name": "Hold User",
            "contact_phone": "+8801712345678",
            "travellers": [{"full_name": "Hold Traveller"}],
        },
    )
    assert r1.status_code == 201
    b1_id = uuid.UUID(r1.json()["id"])

    # Force expires_at into the past
    with get_session_factory()() as db:
        b = db.get(Booking, b1_id)
        assert b is not None
        b.expires_at = utcnow() - timedelta(minutes=5)
        db.commit()
        expired = expire_stale_bookings(db)
        assert expired == 1
        dep = db.get(Departure, dep_id)
        assert dep is not None
        assert dep.seats_booked == 0

    # Create another booking and bulk-cancel departure
    r2 = client.post(
        "/api/v1/bookings",
        headers={**hdr_c, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "departure_id": str(dep_id),
            "seats": 2,
            "contact_name": "Bulk User",
            "contact_phone": "+8801712345678",
            "travellers": [{"full_name": "Bulk Traveller"}],
        },
    )
    assert r2.status_code == 201

    bulk = client.post(
        f"/api/v1/operator/departures/{dep_id}/cancel",
        headers=hdr_a,
        json={"reason": "Cyclone warning"},
    )
    assert bulk.status_code == 200
    assert bulk.json()["cancelled_bookings"] == 1
