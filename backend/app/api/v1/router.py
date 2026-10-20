from fastapi import APIRouter

from app.api.v1 import admin, auth, health, incidents, settings, users

api_router = APIRouter(prefix="/api/v1")
for module in (health, auth, users, incidents, settings, admin):
    api_router.include_router(module.router)
