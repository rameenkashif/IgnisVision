"""RBAC matrix (HANDOFF §6), enforced on the backend. Every new router adds its rows here."""

import uuid

import pytest

from tests.conftest import ROLES

ALL = set(ROLES)
ADMIN = {"admin"}
INCIDENT_READERS = {"admin", "incident_commander"}
X = str(uuid.uuid4())

# (method, path, json body, roles allowed)
MATRIX = [
    ("GET", "/api/v1/auth/me", None, ALL),
    ("PATCH", "/api/v1/auth/me", {"preferred_language": "ur"}, ALL),
    ("POST", "/api/v1/auth/heartbeat", None, ALL),
    ("GET", "/api/v1/settings", None, ALL),
    ("GET", "/api/v1/incidents", None, INCIDENT_READERS),
    ("GET", "/api/v1/users", None, ADMIN),
    ("POST", "/api/v1/users", {"username": "u_rbac", "full_name": "R", "role": "trainee"}, ADMIN),
    ("GET", f"/api/v1/users/{X}", None, ADMIN),
    ("PATCH", f"/api/v1/users/{X}", {"full_name": "Z"}, ADMIN),
    ("POST", f"/api/v1/users/{X}/deactivate", {"confirm": True}, ADMIN),
    ("POST", f"/api/v1/users/{X}/reset-password", {"confirm": True}, ADMIN),
    ("GET", "/api/v1/admin/settings", None, ADMIN),
    ("PATCH", "/api/v1/admin/settings", {"capture_fps": 1}, ADMIN),
    ("GET", "/api/v1/admin/audit-logs", None, ADMIN),
]


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize(("method", "path", "body", "allowed"), MATRIX, ids=lambda v: str(v))
async def test_rbac_matrix(client, as_role, role, method, path, body, allowed):
    _, h = await as_role(role)
    r = await client.request(method, path, json=body, headers=h)
    if role in allowed:
        assert r.status_code not in (401, 403), f"{role} denied {method} {path}: {r.text}"
    else:
        assert r.status_code == 403, f"{role} allowed {method} {path}: {r.status_code}"
        assert r.json()["error"]["code"] == "forbidden"


@pytest.mark.parametrize(("method", "path", "body", "allowed"), MATRIX, ids=lambda v: str(v))
async def test_every_endpoint_requires_auth(client, method, path, body, allowed):
    r = await client.request(method, path, json=body)
    assert r.status_code == 401


async def test_trainee_gets_403_on_incidents(client, as_role):
    """SRS §5.5.1 — called out explicitly in HANDOFF §14 step 9."""
    _, h = await as_role("trainee")
    r = await client.get("/api/v1/incidents", headers=h)
    assert r.status_code == 403


def test_matrix_covers_every_route():
    """Fails when a router is added without RBAC rows (login/refresh/logout/health/mobile are
    credential- or public endpoints and are tested in test_auth / test_health)."""
    from app.main import app

    exempt = {
        "/api/v1/health",
        "/api/v1/health/ready",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
        "/api/v1/auth/change-password",
        "/api/v1/auth/mobile/login",
        "/api/v1/auth/mobile/refresh-bundle",
    }
    covered = {(m, p.replace(X, "{user_id}")) for m, p, _, _ in MATRIX}
    missing = []
    for route in app.routes:
        path = getattr(route, "path", "")
        if not path.startswith("/api/v1") or path in exempt:
            continue
        for m in getattr(route, "methods", set()) - {"HEAD", "OPTIONS"}:
            if (m, path) not in covered:
                missing.append(f"{m} {path}")
    assert not missing, f"routes without RBAC matrix rows: {missing}"
