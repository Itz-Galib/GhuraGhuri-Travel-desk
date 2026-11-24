"""Idempotent Bangladesh demo data seeder (T6.2)."""

import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, utcnow
from app.modules.operators.models import Operator, OperatorMember
from app.modules.tours.models import Departure, Offer, TourPackage
from app.modules.users.models import User

DEMO_PACKAGES = [
    {
        "title": "Sajek Valley 3D2N Cloud Escape",
        "slug": "sajek-valley-3d2n-cloud-escape",
        "destination": "Sajek Valley",
        "summary": "Wake up above the clouds at Ruilui Para with Konglak Hill sunrise trek.",
        "description": (
            "Includes Dhaka-Khagrachari AC bus, Chander Gari transfer, eco-resort stay, "
            "and traditional bamboo chicken lunch."
        ),
        "duration_days": 3,
        "base_price": 650000,
        "advance_percent": 30,
        "cancellation_policy": "Free cancellation up to 7 days before departure.",
    },
    {
        "title": "Sylhet Tea Gardens & Ratargul 2D1N",
        "slug": "sylhet-tea-gardens-ratargul-2d1n",
        "destination": "Sylhet",
        "summary": "Explore Sreemangal tea estates, Lawachara forest, and Ratargul swamp.",
        "description": (
            "Guided eco-tour covering Sreemangal, 7-layer tea cabin, and boat ride in Ratargul."
        ),
        "duration_days": 2,
        "base_price": 480000,
        "advance_percent": 30,
        "cancellation_policy": "50% refund up to 3 days before departure.",
    },
    {
        "title": "Cox's Bazar & Marine Drive Weekend",
        "slug": "coxs-bazar-marine-drive-weekend",
        "destination": "Cox's Bazar",
        "summary": "Sunset at Inani Beach, Himchari viewpoint, and Marine Drive jeep ride.",
        "description": (
            "3-day beach getaway with 3-star hotel near Kolatoli and guided Marine Drive tour."
        ),
        "duration_days": 3,
        "base_price": 750000,
        "advance_percent": 30,
        "cancellation_policy": "Free cancellation up to 5 days before departure.",
    },
    {
        "title": "Sundarbans Kotka Wildlife Vessel Cruise",
        "slug": "sundarbans-kotka-wildlife-cruise",
        "destination": "Sundarbans",
        "summary": "3-day Khulna-to-Kotka mangrove cruise with Jamtola beach trail.",
        "description": (
            "All-inclusive AC cabin vessel from Khulna with forest guard permit and naturalist."
        ),
        "duration_days": 3,
        "base_price": 1150000,
        "advance_percent": 40,
        "cancellation_policy": "Non-refundable within 7 days of departure due to forest permits.",
    },
]


def seed_demo_data(db: Session) -> None:
    now = utcnow()
    admin = db.scalar(select(User).where(User.email == "admin@ghuraghuri.com"))
    if admin is None:
        admin = User(
            id=uuid.uuid4(),
            full_name="GhuraGhuri Admin",
            email="admin@ghuraghuri.com",
            phone="+8801700000099",
            password_hash=hash_password("AdminDemo123!"),
            role="ADMIN",
            status="ACTIVE",
            consented_at=now,
        )
        db.add(admin)
        db.flush()

    op_user = db.scalar(select(User).where(User.email == "operator@ghuraghuri.com"))
    if op_user is None:
        op_user = User(
            id=uuid.uuid4(),
            full_name="Bengal Trails Lead",
            email="operator@ghuraghuri.com",
            phone="+8801800000099",
            password_hash=hash_password("OperatorDemo123!"),
            role="OPERATOR",
            status="ACTIVE",
            consented_at=now,
        )
        db.add(op_user)
        db.flush()

    operator = db.scalar(select(Operator).where(Operator.contact_phone == "+8801800000099"))
    if operator is None:
        operator = Operator(
            id=uuid.uuid4(),
            kind="TOUR",
            type="GROUP",
            display_name="Bengal Trails BD",
            contact_phone="+8801800000099",
            facebook_url="https://facebook.com/groups/bengaltrailsbd",
            payout_methods=[{"provider": "BKASH", "number": "01800000099"}],
            verification_status="APPROVED",
            verified_by=admin.id,
            verified_at=now,
        )
        db.add(operator)
        db.flush()
        db.add(
            OperatorMember(
                operator_id=operator.id,
                user_id=op_user.id,
                member_role="OWNER",
            )
        )

    for idx, item in enumerate(DEMO_PACKAGES):
        pkg = db.scalar(select(TourPackage).where(TourPackage.slug == item["slug"]))
        if pkg is None:
            pkg = TourPackage(
                id=uuid.uuid4(),
                operator_id=operator.id,
                title=str(item["title"]),
                slug=str(item["slug"]),
                destination=str(item["destination"]),
                summary=str(item["summary"]),
                description=str(item["description"]),
                itinerary=[
                    {"day": 1, "title": "Departure from Dhaka"},
                    {"day": 2, "title": f"Explore {item['destination']}"},
                ],
                inclusions=["AC Transport", "Accommodation", "Local Guide"],
                exclusions=["Personal expenses"],
                duration_days=int(str(item["duration_days"])),
                base_price=int(str(item["base_price"])),
                advance_percent=int(str(item["advance_percent"])),
                cancellation_policy=str(item["cancellation_policy"]),
                status="PUBLISHED",
            )
            db.add(pkg)
            db.flush()

            start = date.today() + timedelta(days=14 + idx * 7)
            end = start + timedelta(days=pkg.duration_days - 1)
            db.add(
                Departure(
                    id=uuid.uuid4(),
                    package_id=pkg.id,
                    start_date=start,
                    end_date=end,
                    price=pkg.base_price,
                    capacity=20,
                    status="OPEN",
                )
            )
            if idx == 0:
                db.add(
                    Offer(
                        id=uuid.uuid4(),
                        package_id=pkg.id,
                        title="Winter Cloud 10% Off",
                        discount_type="PERCENT",
                        discount_value=10,
                        starts_at=now - timedelta(days=1),
                        ends_at=now + timedelta(days=30),
                        is_active=True,
                        created_by=admin.id,
                    )
                )

    db.commit()
