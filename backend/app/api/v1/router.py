from fastapi import APIRouter

from app.api.v1 import (
    admin,
    alerts,
    auth,
    capture,
    health,
    help,
    incidents,
    media,
    reports,
    settings,
    status,
    sync,
    teams,
    thermal,
    training,
    training_admin,
    users,
    zones,
)

api_router = APIRouter(prefix="/api/v1")
for module in (
    health, auth, help, users, incidents, zones, teams, alerts, capture, thermal, media, sync,
    reports, training, training_admin, settings, admin, status,
):  # fmt: skip
    api_router.include_router(module.router)
