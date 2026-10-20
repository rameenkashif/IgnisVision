from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.core.security import hash_token, verify_password
from app.db.engine import SessionLocal
from app.models import Incident, RefreshToken, TeamAssignment
from tests.conftest import PASSWORD

REFRESH = "/api/v1/auth/refresh"


async def _set_session(**values) -> None:
    async with SessionLocal() as db:
        await db.execute(update(RefreshToken).values(**values))
        await db.commit()


# --- login -------------------------------------------------------------------------------


async def test_login_success_sets_httponly_secure_strict_cookie(client, make_user):
    u = await make_user("incident_commander", username="Rimsha")
    r = await client.post("/api/v1/auth/login", json={"username": "rimsha", "password": PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer" and body["expires_in"] == 15 * 60
    assert body["idle_timeout_s"] == 30 * 60
    assert body["user"]["id"] == str(u.id) and "password_hash" not in body["user"]
    cookie = r.headers["set-cookie"].lower()
    assert "iv_refresh=" in cookie and "httponly" in cookie and "secure" in cookie
    assert "samesite=strict" in cookie and "path=/api/v1/auth" in cookie


async def test_login_wrong_password_uses_error_envelope(client, make_user):
    u = await make_user()
    r = await client.post(
        "/api/v1/auth/login", json={"username": u.username, "password": "nope12345"}
    )
    assert r.status_code == 401
    assert r.json() == {
        "error": {
            "code": "invalid_credentials",
            "message_key": "errors.invalid_credentials",
            "params": {},
        }
    }


async def test_login_unknown_user_same_error(client):
    r = await client.post("/api/v1/auth/login", json={"username": "ghost", "password": "x1234567"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "invalid_credentials"


async def test_deactivated_user_cannot_login(client, make_user):
    u = await make_user(is_active=False)
    r = await client.post("/api/v1/auth/login", json={"username": u.username, "password": PASSWORD})
    assert r.status_code == 403 and r.json()["error"]["code"] == "account_deactivated"


async def test_protected_endpoint_requires_token(client):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401 and r.json()["error"]["code"] == "not_authenticated"
    r = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "invalid_token"


async def test_me_and_language_preference(client, as_role):
    _, h = await as_role("trainee")
    r = await client.patch("/api/v1/auth/me", json={"preferred_language": "ur"}, headers=h)
    assert r.status_code == 200 and r.json()["preferred_language"] == "ur"
    assert (await client.get("/api/v1/auth/me", headers=h)).json()["preferred_language"] == "ur"


# --- refresh rotation --------------------------------------------------------------------


async def test_refresh_rotates_token(client, as_role):
    await as_role("incident_commander")
    first = client.cookies.get("iv_refresh")
    r = await client.post(REFRESH)
    assert r.status_code == 200, r.text
    second = client.cookies.get("iv_refresh")
    assert second and second != first
    async with SessionLocal() as db:
        rows = (await db.execute(select(RefreshToken))).scalars().all()
    assert len(rows) == 2 and len({r.family_id for r in rows}) == 1
    assert sum(r.revoked_at is None for r in rows) == 1


async def test_reusing_rotated_token_revokes_whole_session(client, as_role):
    await as_role("incident_commander")
    old = client.cookies.get("iv_refresh")
    assert (await client.post(REFRESH)).status_code == 200
    new = client.cookies.get("iv_refresh")
    # Move the old token's rotation outside the race grace window, then replay it.
    async with SessionLocal() as db:
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == hash_token(old))
            .values(revoked_at=datetime.now(UTC) - timedelta(minutes=5))
        )
        await db.commit()
    r = await client.post(REFRESH, json={"refresh_token": old})
    assert r.status_code == 401 and r.json()["error"]["code"] == "refresh_reused"
    r = await client.post(REFRESH, json={"refresh_token": new})
    assert r.status_code == 401  # family revoked: the thief's and the victim's tokens both die


async def test_concurrent_refresh_within_grace_gets_409(client, as_role):
    await as_role("incident_commander")
    old = client.cookies.get("iv_refresh")
    assert (await client.post(REFRESH)).status_code == 200
    r = await client.post(REFRESH, json={"refresh_token": old})
    assert r.status_code == 409 and r.json()["error"]["code"] == "refresh_race"
    assert (await client.post(REFRESH)).status_code == 200  # session still alive


async def test_refresh_without_cookie_is_401(client):
    r = await client.post(REFRESH)
    assert r.status_code == 401


async def test_expired_refresh_token_rejected(client, as_role):
    await as_role("trainee")
    await _set_session(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    r = await client.post(REFRESH)
    assert r.status_code == 401 and r.json()["error"]["code"] == "session_expired"


async def test_logout_revokes_session(client, as_role):
    _, h = await as_role("trainee")
    r = await client.post("/api/v1/auth/logout")
    assert r.status_code == 204
    assert (await client.post(REFRESH)).status_code == 401


# --- idle timeout (SRS §5.3.1) -------------------------------------------------------------


async def test_idle_over_30_minutes_blocks_refresh(client, as_role):
    await as_role("training_staff")
    await _set_session(last_activity_at=datetime.now(UTC) - timedelta(minutes=31))
    r = await client.post(REFRESH)
    assert r.status_code == 401 and r.json()["error"]["code"] == "idle_timeout"


async def test_idle_under_30_minutes_allows_refresh(client, as_role):
    await as_role("training_staff")
    await _set_session(last_activity_at=datetime.now(UTC) - timedelta(minutes=29))
    assert (await client.post(REFRESH)).status_code == 200


async def test_heartbeat_resets_idle_clock(client, as_role):
    _, h = await as_role("field_responder")
    await _set_session(last_activity_at=datetime.now(UTC) - timedelta(minutes=29))
    r = await client.post("/api/v1/auth/heartbeat", headers=h)
    assert r.status_code == 200 and r.json()["in_active_incident"] is False
    await _set_session(last_activity_at=datetime.now(UTC) - timedelta(minutes=10))
    assert (await client.post(REFRESH)).status_code == 200


async def test_refresh_does_not_count_as_activity(client, as_role):
    await as_role("trainee")
    stale = datetime.now(UTC) - timedelta(minutes=20)
    await _set_session(last_activity_at=stale)
    assert (await client.post(REFRESH)).status_code == 200
    async with SessionLocal() as db:
        live = (
            await db.execute(select(RefreshToken).where(RefreshToken.revoked_at.is_(None)))
        ).scalar_one()
    assert abs((live.last_activity_at - stale).total_seconds()) < 1


async def test_commander_of_active_incident_exempt_from_idle(client, as_role):
    commander, _ = await as_role("incident_commander")
    async with SessionLocal() as db:
        db.add(Incident(code="IV-TEST-0001", status="active", commander_id=commander.id))
        await db.commit()
    await _set_session(last_activity_at=datetime.now(UTC) - timedelta(hours=3))
    assert (await client.post(REFRESH)).status_code == 200


async def test_assignee_of_active_incident_exempt_but_not_after_close(client, as_role):
    responder, _ = await as_role("field_responder")
    async with SessionLocal() as db:
        inc = Incident(code="IV-TEST-0002", status="active")
        db.add(inc)
        await db.flush()
        db.add(TeamAssignment(incident_id=inc.id, user_id=responder.id))
        await db.commit()
        inc_id = inc.id
    await _set_session(last_activity_at=datetime.now(UTC) - timedelta(hours=1))
    assert (await client.post(REFRESH)).status_code == 200
    async with SessionLocal() as db:
        await db.execute(update(Incident).where(Incident.id == inc_id).values(status="closed"))
        await db.commit()
    r = await client.post(REFRESH)
    assert r.status_code == 401 and r.json()["error"]["code"] == "idle_timeout"


# --- passwords -----------------------------------------------------------------------------


async def test_password_hashed_with_argon2id(make_user):
    u = await make_user()
    assert u.password_hash.startswith("$argon2id$")
    assert verify_password(u.password_hash, PASSWORD)


async def test_change_password_enforces_policy(client, as_role):
    _, h = await as_role("trainee")
    url = "/api/v1/auth/change-password"
    for bad, code in (
        ("short1", "password_too_short"),
        ("lettersonly", "password_needs_letters_and_numbers"),
        ("12345678", "password_needs_letters_and_numbers"),
    ):
        r = await client.post(
            url, json={"current_password": PASSWORD, "new_password": bad}, headers=h
        )
        assert r.status_code == 422 and r.json()["error"]["code"] == code
    r = await client.post(
        url, json={"current_password": "wrong", "new_password": "Good1234"}, headers=h
    )
    assert r.status_code == 400
    r = await client.post(
        url, json={"current_password": PASSWORD, "new_password": "Good1234"}, headers=h
    )
    assert r.status_code == 204


async def test_must_change_password_blocks_other_endpoints(client, make_user, login):
    u = await make_user("incident_commander", must_change_password=True)
    h = await login(u)
    r = await client.get("/api/v1/incidents", headers=h)
    assert r.status_code == 403 and r.json()["error"]["code"] == "password_change_required"
    assert (await client.get("/api/v1/auth/me", headers=h)).status_code == 200
    r = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "Fresh1234"},
        headers=h,
    )
    assert r.status_code == 204
    assert (await client.get("/api/v1/incidents", headers=h)).status_code == 200


# --- mobile (SRS UC-08 AF1) ------------------------------------------------------------------


async def test_mobile_login_returns_offline_bundle(client, make_user):
    u = await make_user("field_responder")
    r = await client.post(
        "/api/v1/auth/mobile/login",
        json={"username": u.username, "password": PASSWORD, "device_id": "android-1"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "set-cookie" not in r.headers
    b = body["credential_bundle"]
    assert b["user_id"] == str(u.id) and b["role"] == "field_responder"
    assert b["hash_params"]["algorithm"] == "argon2id"
    assert b["hash_params"]["memory_cost"] >= 64 * 1024
    assert verify_password(b["password_hash"], PASSWORD)  # device can verify offline

    # Mobile refresh uses the body token and gets a rotated one back in the body.
    r2 = await client.post(REFRESH, json={"refresh_token": body["refresh_token"]})
    assert r2.status_code == 200 and r2.json()["refresh_token"] != body["refresh_token"]

    h = {"Authorization": f"Bearer {body['access_token']}"}
    r3 = await client.get("/api/v1/auth/mobile/refresh-bundle", headers=h)
    assert r3.status_code == 200 and r3.json()["username"] == u.username


async def test_mobile_bundle_gone_after_deactivation(client, make_user, as_role):
    u = await make_user("field_responder")
    r = await client.post(
        "/api/v1/auth/mobile/login", json={"username": u.username, "password": PASSWORD}
    )
    mobile = r.json()
    h_mobile = {"Authorization": f"Bearer {mobile['access_token']}"}
    _, h_admin = await as_role("admin")
    r = await client.post(
        f"/api/v1/users/{u.id}/deactivate", json={"confirm": True}, headers=h_admin
    )
    assert r.status_code == 200
    r = await client.get("/api/v1/auth/mobile/refresh-bundle", headers=h_mobile)
    assert r.status_code == 410 and r.json()["error"]["code"] == "account_deactivated"
    r = await client.post(REFRESH, json={"refresh_token": mobile["refresh_token"]})
    assert r.status_code == 410
