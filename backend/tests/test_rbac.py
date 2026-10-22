"""RBAC matrix (HANDOFF §6), enforced on the backend. Every new router adds its rows here."""

import uuid

import pytest

from tests.conftest import ROLES

ALL = set(ROLES)
ADMIN = {"admin"}
INCIDENT_READERS = {"admin", "incident_commander"}
COMMANDER = {"incident_commander"}
ATTEMPTERS = {"incident_commander", "field_responder", "training_staff", "trainee"}
X = str(uuid.uuid4())

# (method, path, json body, roles allowed)
MATRIX = [
    ("GET", "/api/v1/auth/me", None, ALL),
    ("PATCH", "/api/v1/auth/me", {"preferred_language": "ur"}, ALL),
    ("POST", "/api/v1/auth/heartbeat", None, ALL),
    ("GET", "/api/v1/settings", None, ALL),
    ("GET", "/api/v1/incidents", None, INCIDENT_READERS),
    ("POST", "/api/v1/incidents", {"address": "A", "floors": 1, "zones_per_floor": 1}, COMMANDER),
    ("GET", f"/api/v1/incidents/{X}", None, INCIDENT_READERS),
    ("PATCH", f"/api/v1/incidents/{X}", {"city": "Lahore"}, COMMANDER),
    ("POST", f"/api/v1/incidents/{X}/activate", None, COMMANDER),
    ("POST", f"/api/v1/incidents/{X}/close", {"confirm": True}, COMMANDER),
    ("GET", f"/api/v1/incidents/{X}/report", None, INCIDENT_READERS),
    ("POST", f"/api/v1/incidents/{X}/report/regenerate", None, COMMANDER),
    ("GET", f"/api/v1/incidents/{X}/report.pdf", None, INCIDENT_READERS),
    ("DELETE", f"/api/v1/incidents/{X}", {"confirm": True}, ADMIN),
    ("GET", f"/api/v1/incidents/{X}/zones", None, INCIDENT_READERS),
    ("PATCH", f"/api/v1/zones/{X}", {"label": "L"}, COMMANDER),
    ("GET", f"/api/v1/zones/{X}/assessments", None, INCIDENT_READERS),
    ("GET", f"/api/v1/incidents/{X}/assignments", None, INCIDENT_READERS),
    ("POST", f"/api/v1/incidents/{X}/assignments", {"user_id": X}, COMMANDER),
    ("DELETE", f"/api/v1/assignments/{X}", None, COMMANDER),
    ("GET", "/api/v1/assignments/mine", None, ALL),
    ("GET", "/api/v1/responders", None, COMMANDER),
    ("GET", "/api/v1/capture/targets", None, {"incident_commander", "field_responder"}),
    (
        "POST",
        f"/api/v1/incidents/{X}/thermal-uploads",
        None,
        {"incident_commander", "field_responder"},
    ),
    ("GET", f"/api/v1/incidents/{X}/thermal-uploads", None, INCIDENT_READERS),
    ("GET", f"/api/v1/jobs/{X}", None, {"incident_commander", "field_responder", "admin"}),
    ("GET", f"/api/v1/incidents/{X}/victims", None, INCIDENT_READERS),
    ("PATCH", f"/api/v1/victims/{X}", {"status": "rescued"}, COMMANDER),
    (
        "POST",
        "/api/v1/sync/incidents",
        {"device_id": "d", "incidents": []},
        {"incident_commander", "field_responder"},
    ),
    ("GET", f"/api/v1/incidents/{X}/alerts", None, INCIDENT_READERS),
    ("POST", f"/api/v1/alerts/{X}/ack", None, COMMANDER),
    ("GET", "/api/v1/users", None, ADMIN),
    ("POST", "/api/v1/users", {"username": "u_rbac", "full_name": "R", "role": "trainee"}, ADMIN),
    ("GET", f"/api/v1/users/{X}", None, ADMIN),
    ("PATCH", f"/api/v1/users/{X}", {"full_name": "Z"}, ADMIN),
    ("POST", f"/api/v1/users/{X}/deactivate", {"confirm": True}, ADMIN),
    ("POST", f"/api/v1/users/{X}/reset-password", {"confirm": True}, ADMIN),
    ("GET", "/api/v1/training/scenarios", None, ATTEMPTERS),
    ("GET", f"/api/v1/training/scenarios/{X}", None, ATTEMPTERS),
    ("POST", f"/api/v1/training/scenarios/{X}/attempts", None, ATTEMPTERS),
    ("POST", f"/api/v1/training/attempts/{X}/submit", {"answers": {}}, ATTEMPTERS),
    ("GET", "/api/v1/training/attempts", None, ALL),
    ("GET", f"/api/v1/training/attempts/{X}", None, ALL),
    ("GET", "/api/v1/admin/scenarios", None, ADMIN),
    ("POST", "/api/v1/admin/scenarios", {"title_en": "t", "title_ur": "t", "kind": "zone"}, ADMIN),
    ("GET", f"/api/v1/admin/scenarios/{X}", None, ADMIN),
    ("PATCH", f"/api/v1/admin/scenarios/{X}", {"is_active": False}, ADMIN),
    ("DELETE", f"/api/v1/admin/scenarios/{X}", {"confirm": True}, ADMIN),
    ("POST", f"/api/v1/admin/scenarios/{X}/items", None, ADMIN),
    ("PATCH", f"/api/v1/admin/scenarios/{X}/items/{X}", {"order": 1}, ADMIN),
    ("DELETE", f"/api/v1/admin/scenarios/{X}/items/{X}", None, ADMIN),
    ("POST", f"/api/v1/admin/scenarios/{X}/recompute-reference", None, ADMIN),
    ("GET", "/api/v1/admin/status", None, ADMIN),
    ("GET", "/api/v1/admin/audit-logs/facets", None, ADMIN),
    ("POST", "/api/v1/help/ask", None, ALL),
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
        "/api/v1/media/{media_id}",  # signed-URL or bearer; tested in test_capture.py
        "/api/v1/media/{media_id}/thumbnail",  # signed-URL or bearer; test_thermal.py
        "/api/v1/media/{media_id}/detections",  # per-incident access; test_thermal.py
        "/api/v1/media/{media_id}/frames",  # per-incident access; test_thermal.py
        "/api/v1/media/{media_id}/frames/{frame_index}",  # signed-URL or bearer
    }
    import re

    def norm(p: str) -> str:
        return re.sub(r"\{[^}]+\}", "{}", p.replace(X, "{}"))

    covered = {(m, norm(p)) for m, p, _, _ in MATRIX}
    missing = []
    for route in app.routes:
        path = getattr(route, "path", "")
        if not path.startswith("/api/v1") or path in exempt:
            continue
        for m in getattr(route, "methods", set()) - {"HEAD", "OPTIONS"}:
            if (m, norm(path)) not in covered:
                missing.append(f"{m} {path}")
    assert not missing, f"routes without RBAC matrix rows: {missing}"
