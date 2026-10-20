"""Refresh-token sessions: rotation, reuse detection and the idle rule (HANDOFF §6)."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import exists, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import hash_token, new_refresh_token
from app.models import Incident, RefreshToken, TeamAssignment, User

# Two tabs refreshing at once both present the same token; the loser gets 409 and retries
# with the cookie the winner just set, instead of tripping reuse detection.
ROTATION_GRACE = timedelta(seconds=10)


def now() -> datetime:
    return datetime.now(UTC)


async def issue(
    db: AsyncSession,
    user: User,
    *,
    device_kind: str,
    user_agent: str | None,
    family_id: uuid.UUID | None = None,
    last_activity_at: datetime | None = None,
) -> tuple[str, RefreshToken]:
    s = get_settings()
    raw = new_refresh_token()
    row = RefreshToken(
        user_id=user.id,
        family_id=family_id or uuid.uuid4(),
        token_hash=hash_token(raw),
        issued_at=now(),
        expires_at=now() + timedelta(days=s.refresh_token_days),
        last_activity_at=last_activity_at or now(),
        user_agent=(user_agent or "")[:400] or None,
        device_kind=device_kind,
    )
    db.add(row)
    await db.flush()
    return raw, row


async def revoke_family(db: AsyncSession, family_id: uuid.UUID) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now())
    )


async def revoke_all_for_user(
    db: AsyncSession, user_id: uuid.UUID, *, except_family: uuid.UUID | None = None
) -> None:
    q = update(RefreshToken).where(
        RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
    )
    if except_family is not None:
        q = q.where(RefreshToken.family_id != except_family)
    await db.execute(q.values(revoked_at=now()))


async def in_active_incident(db: AsyncSession, user_id: uuid.UUID) -> bool:
    """Commander or current assignee of an `active` incident: exempt from idle logout
    (SRS §5.3.1)."""
    assigned = exists().where(
        TeamAssignment.incident_id == Incident.id,
        TeamAssignment.user_id == user_id,
        TeamAssignment.unassigned_at.is_(None),
    )
    q = select(
        exists().where(
            Incident.status == "active",
            Incident.deleted_at.is_(None),
            or_(Incident.commander_id == user_id, assigned),
        )
    )
    return bool((await db.execute(q)).scalar())


async def session_by_id(db: AsyncSession, family_id: uuid.UUID) -> RefreshToken | None:
    q = (
        select(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .order_by(RefreshToken.issued_at.desc())
        .limit(1)
    )
    return (await db.execute(q)).scalar_one_or_none()


async def rotate(
    db: AsyncSession, raw: str | None, *, user_agent: str | None
) -> tuple[str, RefreshToken, User]:
    if not raw:
        raise AppError(401, "not_authenticated")
    row = (
        await db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw)).with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        raise AppError(401, "invalid_token")

    t = now()
    # Checked first so a deactivated device always gets 410 and wipes its offline bundle.
    user = await db.get(User, row.user_id)
    if user is None or not user.is_active:
        await revoke_family(db, row.family_id)
        await db.commit()
        raise AppError(410, "account_deactivated")

    if row.revoked_at is not None:
        if row.replaced_by_id is not None and t - row.revoked_at < ROTATION_GRACE:
            raise AppError(409, "refresh_race")
        # A rotated-out token came back: assume theft and end the whole session.
        await revoke_family(db, row.family_id)
        await db.commit()
        raise AppError(401, "refresh_reused")
    if row.expires_at <= t:
        raise AppError(401, "session_expired")

    idle = timedelta(minutes=get_settings().idle_timeout_minutes)
    if t - row.last_activity_at > idle and not await in_active_incident(db, user.id):
        await revoke_family(db, row.family_id)
        await db.commit()
        raise AppError(401, "idle_timeout")

    new_raw, new_row = await issue(
        db,
        user,
        device_kind=row.device_kind,
        user_agent=user_agent,
        family_id=row.family_id,
        last_activity_at=row.last_activity_at,
    )
    row.revoked_at = t
    row.last_used_at = t
    row.replaced_by_id = new_row.id
    return new_raw, new_row, user


async def touch_activity(db: AsyncSession, family_id: uuid.UUID) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(last_activity_at=now())
    )
