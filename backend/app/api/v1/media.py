import uuid

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from sqlalchemy import exists, select

from app.core.deps import DB, bearer_user
from app.core.errors import AppError
from app.models import Incident, MediaAsset, TeamAssignment, User
from app.services.media import signature_valid
from app.storage.backend import get_storage

router = APIRouter(tags=["media"])


async def _can_view(db: DB, user: User, asset: MediaAsset) -> bool:
    if asset.incident_id is None:  # training media (Phase 7): any signed-in user
        return True
    if user.role in ("incident_commander", "admin"):
        return True
    if user.role != "field_responder":
        return False
    inc = await db.get(Incident, asset.incident_id)
    if inc and inc.status == "active":
        return True
    q = select(
        exists().where(
            TeamAssignment.incident_id == asset.incident_id, TeamAssignment.user_id == user.id
        )
    )
    return bool((await db.execute(q)).scalar())


@router.get("/media/{media_id}", response_class=FileResponse)
async def get_media(
    media_id: uuid.UUID,
    request: Request,
    db: DB,
    exp: int | None = None,
    sig: str | None = None,
) -> FileResponse:
    """Auth: a valid short-lived signature (for <img>/<video>), or a bearer token with access
    to the incident. Supports HTTP Range (video seeking)."""
    asset = await db.get(MediaAsset, media_id)
    if asset is None:
        raise AppError(404, "media_not_found")
    if not signature_valid(media_id, exp, sig):
        user = await bearer_user(request, db)
        if not await _can_view(db, user, asset):
            raise AppError(403, "forbidden")
    path = get_storage().path(asset.storage_key)
    if not path.exists():
        raise AppError(404, "media_not_found")
    return FileResponse(
        path, media_type=asset.mime, headers={"Cache-Control": "private, max-age=600"}
    )
