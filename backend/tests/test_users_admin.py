from sqlalchemy import select

from app.db.engine import SessionLocal
from app.models import AuditLog


async def _audit(action: str) -> list[AuditLog]:
    async with SessionLocal() as db:
        return list((await db.execute(select(AuditLog).where(AuditLog.action == action))).scalars())


async def test_admin_creates_user_with_temp_password_and_audit(client, as_role):
    admin, h = await as_role("admin")
    r = await client.post(
        "/api/v1/users",
        json={"username": "responder2", "full_name": "Ali Raza", "role": "field_responder"},
        headers=h,
    )
    assert r.status_code == 201, r.text
    temp = r.json()["temporary_password"]
    assert temp and r.json()["user"]["must_change_password"] is True
    [entry] = await _audit("user.create")
    assert entry.actor_user_id == admin.id and entry.after["username"] == "responder2"
    assert "password_hash" not in entry.after

    r = await client.post("/api/v1/auth/login", json={"username": "RESPONDER2", "password": temp})
    assert r.status_code == 200 and r.json()["user"]["must_change_password"] is True


async def test_username_unique_case_insensitive(client, as_role, make_user):
    await make_user(username="Commander9")
    _, h = await as_role("admin")
    r = await client.post(
        "/api/v1/users",
        json={"username": "commander9", "full_name": "X", "role": "trainee"},
        headers=h,
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "username_taken"


async def test_create_user_rejects_weak_password(client, as_role):
    _, h = await as_role("admin")
    r = await client.post(
        "/api/v1/users",
        json={"username": "weak", "full_name": "W", "role": "trainee", "password": "abcdefgh"},
        headers=h,
    )
    assert r.status_code == 422


async def test_update_user_role_audited_and_sessions_revoked(client, as_role, make_user, login):
    target = await make_user("trainee")
    await login(target)
    target_cookie = client.cookies.get("iv_refresh")
    _, h = await as_role("admin")
    r = await client.patch(
        f"/api/v1/users/{target.id}", json={"role": "field_responder"}, headers=h
    )
    assert r.status_code == 200 and r.json()["role"] == "field_responder"
    [entry] = await _audit("user.update")
    assert entry.before["role"] == "trainee" and entry.after["role"] == "field_responder"
    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": target_cookie})
    assert r.status_code == 401


async def test_deactivate_requires_confirmation_and_is_audited(client, as_role, make_user):
    target = await make_user("field_responder")
    _, h = await as_role("admin")
    url = f"/api/v1/users/{target.id}/deactivate"
    r = await client.post(url, json={"confirm": False}, headers=h)
    assert r.status_code == 400 and r.json()["error"]["code"] == "confirmation_required"
    r = await client.post(url, json={"confirm": True}, headers=h)
    assert r.status_code == 200 and r.json()["is_active"] is False
    assert len(await _audit("user.deactivate")) == 1


async def test_admin_cannot_deactivate_or_demote_self(client, as_role):
    admin, h = await as_role("admin")
    r = await client.post(f"/api/v1/users/{admin.id}/deactivate", json={"confirm": True}, headers=h)
    assert r.status_code == 409
    r = await client.patch(f"/api/v1/users/{admin.id}", json={"role": "trainee"}, headers=h)
    assert r.status_code == 409


async def test_reset_password_forces_change(client, as_role, make_user):
    target = await make_user("trainee")
    _, h = await as_role("admin")
    r = await client.post(
        f"/api/v1/users/{target.id}/reset-password", json={"confirm": True}, headers=h
    )
    assert r.status_code == 200
    temp = r.json()["temporary_password"]
    r = await client.post(
        "/api/v1/auth/login", json={"username": target.username, "password": temp}
    )
    assert r.json()["user"]["must_change_password"] is True
    assert len(await _audit("user.reset_password")) == 1


async def test_list_users_filters(client, as_role, make_user):
    await make_user("trainee", full_name="Sana Trainee")
    _, h = await as_role("admin")
    r = await client.get("/api/v1/users", params={"role": "trainee"}, headers=h)
    assert r.status_code == 200 and r.json()["total"] == 1
    r = await client.get("/api/v1/users", params={"q": "sana"}, headers=h)
    assert r.json()["items"][0]["full_name"] == "Sana Trainee"


async def test_audit_log_endpoint(client, as_role, make_user):
    target = await make_user("trainee")
    _, h = await as_role("admin")
    await client.post(f"/api/v1/users/{target.id}/deactivate", json={"confirm": True}, headers=h)
    r = await client.get(
        "/api/v1/admin/audit-logs", params={"entity_id": str(target.id)}, headers=h
    )
    assert r.status_code == 200 and r.json()["items"][0]["action"] == "user.deactivate"


# --- settings ----------------------------------------------------------------------------


async def test_public_settings_subset(client, as_role):
    _, h = await as_role("trainee")
    r = await client.get("/api/v1/settings", headers=h)
    assert r.status_code == 200
    assert r.json()["evacuation_threshold_pct"] == 40
    assert "rpi.weights" not in r.json()


async def test_admin_updates_settings_with_validation_and_audit(client, as_role):
    _, h = await as_role("admin")
    r = await client.patch(
        "/api/v1/admin/settings",
        json={"evacuation_threshold_pct": 45, "rpi.weights": {"w_p": 0.7, "w_c": 0.3, "w_r": 0}},
        headers=h,
    )
    assert r.status_code == 200, r.text
    assert r.json()["evacuation_threshold_pct"] == 45 and r.json()["rpi.weights"]["w_r"] == 0
    [entry] = await _audit("settings.update")
    assert entry.before["evacuation_threshold_pct"] == 40

    for bad in (
        {"evacuation_threshold_pct": 140},
        {"rpi.bands": {"critical": 0.3, "high": 0.5, "medium": 0.2}},
        {"rpi.weights": {"w_p": 1.5, "w_c": 0, "w_r": 0}},
        {"not.a.key": 1},
    ):
        r = await client.patch("/api/v1/admin/settings", json=bad, headers=h)
        assert r.status_code == 422, bad
        assert r.json()["error"]["code"] == "invalid_setting"
