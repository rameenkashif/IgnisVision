from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.core.config import get_settings
from app.db.engine import engine

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    s = get_settings()
    return {"status": "ok", "service": s.app_name, "version": s.version, "ml_backend": s.ml_backend}


@router.get("/health/ready")
async def ready(response: Response) -> dict:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable", "db": "down"}
    return {"status": "ok", "db": "up"}
