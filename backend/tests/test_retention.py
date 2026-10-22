from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.db.engine import SessionLocal
from app.models import AuditLog, Incident, MediaAsset
from app.services import retention
from app.services.media import store_media


async def _incident(client, h, create_incident, close: bool) -> dict:
    inc = await create_incident(h)
    if close:
        await client.post(f"/api/v1/incidents/{inc['id']}/activate", headers=h)
        r = await client.post(
            f"/api/v1/incidents/{inc['id']}/close", json={"confirm": True}, headers=h
        )
        assert r.status_code == 200
    return inc


async def test_retention_off_by_default(client, as_role, create_incident):
    _, h = await as_role("incident_commander")
    await _incident(client, h, create_incident, close=True)
    async with SessionLocal() as db:
        r = await retention.purge(db, now=datetime.now(UTC) + timedelta(days=9999))
    assert r.enabled is False


async def test_retention_removes_only_old_closed_or_deleted(client, as_role, create_incident):
    _, h = await as_role("incident_commander")
    _, ha = await as_role("admin")
    old = await _incident(client, h, create_incident, close=True)
    recent = await _incident(client, h, create_incident, close=True)
    open_ = await _incident(client, h, create_incident, close=False)
    deleted = await _incident(client, h, create_incident, close=False)
    await client.request(
        "DELETE", f"/api/v1/incidents/{deleted['id']}", json={"confirm": True}, headers=ha
    )
    await client.patch("/api/v1/admin/settings", json={"retention_days": 30}, headers=ha)
    long_ago = datetime.now(UTC) - timedelta(days=45)
    async with SessionLocal() as db:
        await db.execute(
            update(Incident)
            .where(Incident.id.in_([old["id"], deleted["id"]]))
            .values(closed_at=long_ago, deleted_at=None)
        )
        await db.execute(
            update(Incident).where(Incident.id == deleted["id"]).values(deleted_at=long_ago)
        )
        await db.execute(  # an open incident started long ago is never removed
            update(Incident).where(Incident.id == open_["id"]).values(opened_at=long_ago)
        )
        asset = await store_media(
            db, key=f"incidents/{old['id']}/x.jpg", data=b"jpeg", kind="rgb_frame",
            mime="image/jpeg", source="capture", incident_id=old["id"],
        )  # fmt: skip
        key = asset.storage_key
        await db.commit()
    from app.storage.backend import get_storage

    path = get_storage().path(key)
    assert path.exists()

    async with SessionLocal() as db:
        dry = await retention.purge(db, dry_run=True)
    assert sorted(dry.incidents) == sorted([old["code"], deleted["code"]])

    async with SessionLocal() as db:
        res = await retention.purge(db)
    assert res.files == 1 and not path.exists()
    async with SessionLocal() as db:
        left = set((await db.execute(select(Incident.code))).scalars())
        assert left == {recent["code"], open_["code"]}
        assert (
            await db.execute(select(MediaAsset).where(MediaAsset.storage_key == key))
        ).first() is None
        log = (
            await db.execute(select(AuditLog).where(AuditLog.action == "retention.purge"))
        ).scalar_one()
        assert sorted(log.before["incidents"]) == sorted([old["code"], deleted["code"]])
