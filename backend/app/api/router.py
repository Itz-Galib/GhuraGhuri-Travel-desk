"""Versioned API router. Module routers are mounted here as they are built."""

from fastapi import APIRouter

from app.jobs.sweeper import internal_router as cron_router
from app.modules.admin.router import admin_router, operator_dash_router
from app.modules.auth.router import me_router
from app.modules.auth.router import router as auth_router
from app.modules.bookings.router import customer_router as bookings_router
from app.modules.bookings.router import operator_router as operator_bookings_router
from app.modules.notifications.router import router as notifications_router
from app.modules.operators.router import admin_router as admin_operators_router
from app.modules.operators.router import router as operators_router
from app.modules.tours.router import operator_router as operator_tours_router
from app.modules.tours.router import public_router as public_tours_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(me_router)
api_router.include_router(operators_router)
api_router.include_router(admin_operators_router)
api_router.include_router(operator_tours_router)
api_router.include_router(public_tours_router)
api_router.include_router(bookings_router)
api_router.include_router(operator_bookings_router)
api_router.include_router(notifications_router)
api_router.include_router(cron_router)
api_router.include_router(admin_router)
api_router.include_router(operator_dash_router)
