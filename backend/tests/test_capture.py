"""Zone capture end to end over the WebSocket (HANDOFF §7.3, Phase 4 exit)."""

import asyncio
import io
import time

import numpy as np
import pytest
from PIL import Image
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.ml.mock import ScenarioClock
from app.ml.mock.models import MockBuildingSegmenter, MockDamageSegmenter, MockThermalPose
from app.ml.registry import Models, set_models
from tests.conftest import PASSWORD

INC = {"address": "Mall Road", "floors": 1, "zones_per_floor": 2}


class FakeClock:
    t = 5000.0

    def __call__(self):
        return self.t


def jpeg(seed: int = 1, grey: bool = False) -> bytes:
    arr = (
        np.full((240, 320, 3), 128, np.uint8)
        if grey
        else np.random.default_rng(seed).integers(0, 255, (240, 320, 3), dtype=np.uint8)
    )
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, "JPEG", quality=70)
    return buf.getvalue()


@pytest.fixture
def clock():
    c = FakeClock()
    set_models(
        Models("mock", MockThermalPose(), MockBuildingSegmenter(),
               MockDamageSegmenter(ScenarioClock("escalating", c)))
    )  # fmt: skip
    yield c
    set_models(None)


@pytest.fixture
def tc():
    with TestClient(app, base_url="https://testserver") as c:
        yield c


def login(tc, username):
    r = tc.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
    return r.json()["access_token"]


@pytest.fixture
def setup(tc, make_user):
    cmd = asyncio.run(make_user("incident_commander"))
    resp = asyncio.run(make_user("field_responder"))
    trainee = asyncio.run(make_user("trainee"))
    h = {"Authorization": f"Bearer {login(tc, cmd.username)}"}
    inc = tc.post("/api/v1/incidents", json=INC, headers=h).json()
    tc.post(f"/api/v1/incidents/{inc['id']}/activate", headers=h)
    return {"h": h, "inc": inc, "resp": resp.username, "trainee": trainee.username}


def start(ws, token, zone_id):
    ws.send_json({"type": "auth", "token": token})
    ws.send_json({"type": "start", "zone_id": zone_id})
    return ws.receive_json()


def next_of(ws, type_, limit=10):
    for _ in range(limit):
        m = ws.receive_json()
        if m["type"] == type_:
            return m
    raise AssertionError(type_)


def test_responder_stream_updates_zone_within_6s(tc, setup, clock):
    zone = setup["inc"]["zones"][0]
    with tc.websocket_connect("/ws/capture") as ws:
        started = start(ws, login(tc, setup["resp"]), zone["id"])
        assert started["type"] == "started" and started["target_fps"] == 1.0
        t0 = time.perf_counter()
        ws.send_bytes(jpeg())
        res = next_of(ws, "zone_result")
        assert time.perf_counter() - t0 < 6.0  # SRS: zone update within 6 s
        assert res["status"] == "safe" and res["analysable"] is True
        assert res["frame_url"].startswith("/api/v1/media/") and res["overlay_url"]
        ws.send_json({"type": "stop"})
    d = tc.get(f"/api/v1/incidents/{setup['inc']['id']}", headers=setup["h"]).json()
    z = next(z for z in d["zones"] if z["id"] == zone["id"])
    assert z["status"] == "safe" and z["frame_url"] and z["reasons"]
    assert d["kpis"]["classified"] == 1 and d["kpis"]["ai_confidence"] is not None
    # Signed frame URL works without a bearer token (for <img>); tampering is refused.
    assert tc.get(z["frame_url"]).headers["content-type"] == "image/jpeg"
    assert tc.get(z["frame_url"].replace("sig=", "sig=0")).status_code == 401


def test_rapid_change_raises_critical_alert(tc, setup, clock):
    zone = setup["inc"]["zones"][1]
    with tc.websocket_connect("/ws/capture") as ws:
        start(ws, login(tc, setup["resp"]), zone["id"])
        seen = []
        for i in range(4):  # t = 0, 9, 18, 27 s → safe, caution, unsafe, unsafe
            ws.send_bytes(jpeg(i))
            seen.append(next_of(ws, "zone_result")["status"])
            if seen[-1] == "unsafe" and len(seen) == 3:
                alert = next_of(ws, "alert")
                assert alert["severity"] == "crit" and alert["alert_type"] == "zone_rapid_change"
                assert alert["params"] == {"zone": zone["code"], "from": "caution", "to": "unsafe"}
            clock.t += 9
        ws.send_json({"type": "stop"})
    assert seen == ["safe", "caution", "unsafe", "unsafe"]
    alerts = tc.get(f"/api/v1/incidents/{setup['inc']['id']}/alerts", headers=setup["h"]).json()
    kinds = [a["type"] for a in alerts["items"]]
    assert kinds.count("zone_rapid_change") == 1  # only on the transition, not every frame


def test_unanalysable_frame_keeps_previous_status_and_alerts_once(tc, setup, clock):
    zone = setup["inc"]["zones"][0]
    with tc.websocket_connect("/ws/capture") as ws:
        start(ws, login(tc, setup["resp"]), zone["id"])
        ws.send_bytes(jpeg())
        assert next_of(ws, "zone_result")["status"] == "safe"
        for _ in range(3):
            ws.send_bytes(jpeg(grey=True))
            r = next_of(ws, "zone_result")
            assert r["analysable"] is False and r["status"] == "safe"  # previous status kept
        ws.send_json({"type": "stop"})
    items = tc.get(f"/api/v1/incidents/{setup['inc']['id']}/alerts", headers=setup["h"]).json()
    assert [a["type"] for a in items["items"]].count("analysis_failed") == 1


def test_never_safe_from_smoke_alone(tc, setup, clock):
    zone = setup["inc"]["zones"][1]
    with tc.websocket_connect("/ws/capture") as ws:
        start(ws, login(tc, setup["resp"]), zone["id"])
        ws.send_bytes(jpeg(grey=True))
        assert next_of(ws, "zone_result")["status"] == "unclassified"
        ws.send_json({"type": "stop"})


def test_bad_frames_and_unclean_disconnect(tc, setup, clock):
    zone = setup["inc"]["zones"][0]
    with tc.websocket_connect("/ws/capture") as ws:
        start(ws, login(tc, setup["resp"]), zone["id"])
        ws.send_bytes(b"not a jpeg")
        assert next_of(ws, "error")["code"] == "not_jpeg"
    # dropped without "stop" → camera_lost info alert (written as the server cleans up)
    for _ in range(40):
        items = tc.get(f"/api/v1/incidents/{setup['inc']['id']}/alerts", headers=setup["h"]).json()
        if "camera_lost" in [a["type"] for a in items["items"]]:
            break
        time.sleep(0.05)
    assert "camera_lost" in [a["type"] for a in items["items"]]


def test_capture_rules(tc, setup, clock):
    zone = setup["inc"]["zones"][0]
    with tc.websocket_connect("/ws/capture") as ws:
        r = start(ws, login(tc, setup["trainee"]), zone["id"])
        assert r == {"type": "error", "code": "zone_not_capturable"}
        with pytest.raises(WebSocketDisconnect) as e:
            ws.receive_json()
        assert e.value.code == 4403
    # Dispatched (not yet active) incidents can't be captured.
    other = tc.post("/api/v1/incidents", json=INC, headers=setup["h"]).json()
    with tc.websocket_connect("/ws/capture") as ws:
        assert start(ws, login(tc, setup["resp"]), other["zones"][0]["id"])["type"] == "error"


def test_capture_targets_list_active_incident_zones(tc, setup, clock):
    h = {"Authorization": f"Bearer {login(tc, setup['resp'])}"}
    targets = tc.get("/api/v1/capture/targets", headers=h).json()
    assert [t["incident"]["id"] for t in targets] == [setup["inc"]["id"]]
    assert [z["code"] for z in targets[0]["zones"]] == ["F1-Z1", "F1-Z2"]
    h_t = {"Authorization": f"Bearer {login(tc, setup['trainee'])}"}
    assert tc.get("/api/v1/capture/targets", headers=h_t).status_code == 403


def test_media_bearer_access_rules(tc, setup, clock):
    zone = setup["inc"]["zones"][0]
    with tc.websocket_connect("/ws/capture") as ws:
        start(ws, login(tc, setup["resp"]), zone["id"])
        ws.send_bytes(jpeg())
        url = next_of(ws, "zone_result")["frame_url"].split("?")[0]
        ws.send_json({"type": "stop"})
    assert tc.get(url).status_code == 401
    assert tc.get(url, headers=setup["h"]).status_code == 200
    h_t = {"Authorization": f"Bearer {login(tc, setup['trainee'])}"}
    assert tc.get(url, headers=h_t).status_code == 403
