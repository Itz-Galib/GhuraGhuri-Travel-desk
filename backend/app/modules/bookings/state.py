"""Centralized booking state machine (spec 01 & 03)."""

from app.core.errors import ConflictError

ACTIVE_STATES = frozenset(
    {
        "PENDING_PAYMENT",
        "AWAITING_VERIFICATION",
        "CONFIRMED",
        "CANCELLATION_REQUESTED",
        "COMPLETED",
    }
)

SEAT_RELEASING_STATES = frozenset(
    {
        "EXPIRED",
        "REJECTED",
        "CANCELLED",
        "CANCELLED_UNAVAILABLE",
    }
)

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "PENDING_PAYMENT": frozenset(
        {
            "AWAITING_VERIFICATION",
            "CONFIRMED",
            "EXPIRED",
            "REJECTED",
            "CANCELLED",
            "CANCELLED_UNAVAILABLE",
        }
    ),
    "AWAITING_VERIFICATION": frozenset(
        {
            "CONFIRMED",
            "REJECTED",
            "CANCELLED_UNAVAILABLE",
        }
    ),
    "CONFIRMED": frozenset(
        {
            "COMPLETED",
            "CANCELLATION_REQUESTED",
            "CANCELLED_UNAVAILABLE",
        }
    ),
    "CANCELLATION_REQUESTED": frozenset(
        {
            "CANCELLED",
            "CONFIRMED",
            "CANCELLED_UNAVAILABLE",
        }
    ),
    "COMPLETED": frozenset(),
    "EXPIRED": frozenset(),
    "REJECTED": frozenset(),
    "CANCELLED": frozenset(),
    "CANCELLED_UNAVAILABLE": frozenset(),
}


def validate_transition(from_status: str, to_status: str) -> None:
    allowed = ALLOWED_TRANSITIONS.get(from_status)
    if allowed is None or to_status not in allowed:
        raise ConflictError(
            f"Illegal booking transition from {from_status} to {to_status}",
            code="ILLEGAL_TRANSITION",
        )


def should_release_seats(from_status: str, to_status: str) -> bool:
    return from_status in ACTIVE_STATES and to_status in SEAT_RELEASING_STATES
