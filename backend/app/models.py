"""Import all models so metadata and Alembic see the full schema."""

from app.modules.audit.models import AuditLog
from app.modules.bookings.models import (
    Booking,
    BookingEvent,
    BookingTraveller,
    IdempotencyKey,
    Payment,
)
from app.modules.notifications.models import Notification
from app.modules.operators.models import (
    Operator,
    OperatorMember,
    VerificationDocument,
)
from app.modules.tours.models import Departure, Offer, TourPackage, TourPackageImage
from app.modules.users.models import RefreshToken, User

__all__ = [
    "AuditLog",
    "Booking",
    "BookingEvent",
    "BookingTraveller",
    "Departure",
    "IdempotencyKey",
    "Notification",
    "Offer",
    "Operator",
    "OperatorMember",
    "Payment",
    "RefreshToken",
    "TourPackage",
    "TourPackageImage",
    "User",
    "VerificationDocument",
]
