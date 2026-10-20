from fastapi import APIRouter

from app.api.v1 import (
    admin,
    alerts,
    auth,
    capture,
    health,
    incidents,
    media,
    settings,
    teams,
    users,
    zones,
)

api_router = APIRouter(prefix="/api/v1")
for module in (
    health,
    auth,
    users,
    incidents,
    zones,
    teams,
    alerts,
    capture,
    media,
    settings,
    admin,
):
    api_router.include_router(module.router)
