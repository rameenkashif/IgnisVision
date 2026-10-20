"""WebSocket channels (HANDOFF §7.2). Sync tests: Starlette's TestClient drives the app on
its own loop, and REST calls through the same client publish onto the same event bus."""

import asyncio

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from tests.conftest import PASSWORD

INC = {"address": "Mall Road", "floors": 1, "zones_per_floor": 2}


@pytest.fixture
def tc():
    with TestClient(app, base_url="https://testserver") as c:
        yield c


def _login(tc: TestClient, username: str) -> str:
    r = tc.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def users(make_user):
    out = {}
    for role in ("incident_commander", "admin", "field_responder", "trainee"):
        out[role] = asyncio.run(make_user(role)).username
    return out


def _until(ws, type_: str, limit: int = 10) -> dict:
    for _ in range(limit):
        msg = ws.receive_json()
        if msg["type"] == type_:
            return msg
    raise AssertionError(f"no {type_} event")


def test_incident_channel_streams_updates(tc, users):
    token = _login(tc, users["incident_commander"])
    h = {"Authorization": f"Bearer {token}"}
    inc = tc.post("/api/v1/incidents", json=INC, headers=h).json()
    with tc.websocket_connect(f"/ws/incidents/{inc['id']}") as ws:
        ws.send_json({"type": "auth", "token": token})
        assert ws.receive_json() == {"type": "ready", "incident_id": inc["id"]}
        tc.post(f"/api/v1/incidents/{inc['id']}/activate", headers=h)
        ev = _until(ws, "incident.updated")
        assert ev["incident"]["status"] == "active"
        assert ev["incident"]["kpis"]["zones_total"] == 2
        ws.send_json({"type": "ping"})
        assert _until(ws, "pong") == {"type": "pong"}


def test_second_viewer_sees_new_incident_on_station_channel(tc, users):
    admin_token = _login(tc, users["admin"])
    cmd = {"Authorization": f"Bearer {_login(tc, users['incident_commander'])}"}
    with tc.websocket_connect("/ws/station") as ws:
        ws.send_json({"type": "auth", "token": admin_token})
        assert ws.receive_json()["type"] == "ready"
        inc = tc.post("/api/v1/incidents", json=INC, headers=cmd).json()
        ev = _until(ws, "incident.created")
        assert ev["incident"]["id"] == inc["id"] and ev["incident"]["status"] == "dispatched"


def test_assignment_changes_are_pushed(tc, users, make_user):
    token = _login(tc, users["incident_commander"])
    h = {"Authorization": f"Bearer {token}"}
    responder = asyncio.run(make_user("field_responder"))
    inc = tc.post("/api/v1/incidents", json=INC, headers=h).json()
    with tc.websocket_connect(f"/ws/incidents/{inc['id']}") as ws:
        ws.send_json({"type": "auth", "token": token})
        ws.receive_json()
        tc.post(
            f"/api/v1/incidents/{inc['id']}/assignments",
            json={"user_id": str(responder.id), "zone_id": inc["zones"][1]["id"]},
            headers=h,
        )
        ev = _until(ws, "assignment.changed")
        assert ev["assignment"]["zone_code"] == "F1-Z2"
        assert ev["assignment"]["user"]["id"] == str(responder.id)


@pytest.mark.parametrize(
    ("first", "code"),
    [({"type": "hello"}, "auth_required"), ({"type": "auth", "token": "junk"}, "invalid_token")],
)
def test_rejects_missing_or_bad_auth(tc, users, first, code):
    h = {"Authorization": f"Bearer {_login(tc, users['incident_commander'])}"}
    inc = tc.post("/api/v1/incidents", json=INC, headers=h).json()
    with tc.websocket_connect(f"/ws/incidents/{inc['id']}") as ws:
        ws.send_json(first)
        assert ws.receive_json() == {"type": "error", "code": code}
        with pytest.raises(WebSocketDisconnect) as e:
            ws.receive_json()
        assert e.value.code == 4401


def test_trainee_forbidden_and_responder_rules(tc, users):
    h = {"Authorization": f"Bearer {_login(tc, users['incident_commander'])}"}
    inc = tc.post("/api/v1/incidents", json=INC, headers=h).json()
    for username, expect in ((users["trainee"], 4403), (users["field_responder"], 4403)):
        with tc.websocket_connect(f"/ws/incidents/{inc['id']}") as ws:
            ws.send_json({"type": "auth", "token": _login(tc, username)})
            assert ws.receive_json()["code"] == "forbidden"
            with pytest.raises(WebSocketDisconnect) as e:
                ws.receive_json()
            assert e.value.code == expect
    # Once the incident is active, any responder may watch it (for zone capture).
    tc.post(f"/api/v1/incidents/{inc['id']}/activate", headers=h)
    with tc.websocket_connect(f"/ws/incidents/{inc['id']}") as ws:
        ws.send_json({"type": "auth", "token": _login(tc, users["field_responder"])})
        assert ws.receive_json()["type"] == "ready"
    # Trainees never get the station channel either.
    with tc.websocket_connect("/ws/station") as ws:
        ws.send_json({"type": "auth", "token": _login(tc, users["trainee"])})
        assert ws.receive_json()["code"] == "forbidden"


def test_unknown_incident_is_4404(tc, users):
    import uuid

    with tc.websocket_connect(f"/ws/incidents/{uuid.uuid4()}") as ws:
        ws.send_json({"type": "auth", "token": _login(tc, users["incident_commander"])})
        assert ws.receive_json()["code"] == "incident_not_found"
