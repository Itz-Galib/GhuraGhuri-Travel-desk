"""Health endpoints: liveness and readiness (DB check)."""

import logging

from fastapi import APIRouter, Response, status
from sqlalchemy.exc import SQLAlchemyError

from app.core.db import check_database

logger = logging.getLogger("app.health")

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness probe")
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get(
    "/health/ready",
    summary="Readiness probe (checks the database)",
    responses={503: {"description": "Database unavailable"}},
)
def readiness(response: Response) -> dict[str, str]:
    try:
        check_database()
    except SQLAlchemyError:
        logger.warning("database readiness check failed", exc_info=True)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "degraded", "database": "unavailable"}
    return {"status": "ok", "database": "ok"}
