"""Media assets and signed URLs. <img>/<video> can't send a bearer token, so URLs handed to an
authorised client carry a short-lived HMAC signature instead (see docs/DECISIONS.md)."""

import hashlib
import hmac
import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import MediaAsset
from app.storage.backend import get_storage

URL_TTL_S = 15 * 60


def _sig(media_id: str, exp: int) -> str:
    key = get_settings().jwt_secret.encode()
    return hmac.new(key, f"media:{media_id}:{exp}".encode(), hashlib.sha256).hexdigest()[:32]


def media_url(media_id: uuid.UUID | str | None) -> str | None:
    if media_id is None:
        return None
    exp = int(time.time()) + URL_TTL_S
    exp -= exp % 60  # stable for a minute, so cached images aren't re-downloaded every frame
    return f"/api/v1/media/{media_id}?exp={exp}&sig={_sig(str(media_id), exp)}"


def signature_valid(media_id: uuid.UUID, exp: int | None, sig: str | None) -> bool:
    if exp is None or sig is None or exp < time.time():
        return False
    return hmac.compare_digest(_sig(str(media_id), exp), sig)


async def store_media(
    db: AsyncSession,
    *,
    key: str,
    data: bytes,
    kind: str,
    mime: str,
    source: str,
    incident_id: uuid.UUID | None = None,
    uploaded_by: uuid.UUID | None = None,
    width: int | None = None,
    height: int | None = None,
    duration_s: float | None = None,
) -> MediaAsset:
    get_storage().save(key, data)
    asset = MediaAsset(
        incident_id=incident_id,
        kind=kind,
        storage_key=key,
        mime=mime,
        bytes=len(data),
        width=width,
        height=height,
        duration_s=duration_s,
        sha256=hashlib.sha256(data).hexdigest(),
        uploaded_by=uploaded_by,
        source=source,
    )
    db.add(asset)
    await db.flush()
    return asset
