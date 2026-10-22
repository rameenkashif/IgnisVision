"""Mobile sync contract (HANDOFF §7.4): idempotent per client_uuid, RPI recomputed."""

import io
import json

import numpy as np
from PIL import Image


def payload(client_uuid="c0b4-0001", **over):
    det = {
        "client_detection_uuid": f"{client_uuid}-d1",
        "captured_at": "2026-10-20T10:00:00Z",
        "mode": "live",
        "track_id": 3,
        "bbox": [0.2, 0.3, 0.4, 0.9],
        "keypoints": [[0.3, 0.4, 0.9]] * 17,
        "posture": "lying",
        "posture_confidence": 0.81,
        "low_confidence": False,
        "detection_confidence": 0.88,
        "env_risk": 0.0,
        "rpi_score": 0.86,
        "rpi_band": "critical",
    }
    inc = {
        "client_uuid": client_uuid,
        "started_at": "2026-10-20T09:55:00Z",
        "ended_at": "2026-10-20T10:20:00Z",
        "label": "Anarkali basement",
        "linked_incident_id": None,
        "detections": [det, {**det, "client_detection_uuid": f"{client_uuid}-d2",
                             "captured_at": "2026-10-20T10:00:01Z", "posture_confidence": 0.5}],
    }  # fmt: skip
    inc.update(over)
    return {"device_id": "android-abc", "app_version": "1.0.0", "incidents": [inc]}


async def test_sync_creates_once_and_dedupes(client, as_role):
    _, h = await as_role("field_responder")
    r = await client.post("/api/v1/sync/incidents", json=payload(), headers=h)
    assert r.status_code == 200, r.text
    [res] = r.json()["results"]
    assert res["status"] == "created"
    r2 = await client.post("/api/v1/sync/incidents", json=payload(), headers=h)
    [res2] = r2.json()["results"]
    assert r2.status_code == 200 and res2["status"] == "duplicate"
    assert res2["incident_id"] == res["incident_id"]

    _, hc = await as_role("incident_commander")
    inc = (await client.get(f"/api/v1/incidents/{res['incident_id']}", headers=hc)).json()
    assert inc["source"] == "mobile_sync" and inc["status"] == "closed"
    victims = (
        await client.get(f"/api/v1/incidents/{res['incident_id']}/victims", headers=hc)
    ).json()
    assert len(victims) == 1  # same track_id → one person
    v = victims[0]
    assert v["source"] == "mobile_sync" and v["posture"] == "lying"
    # Server recomputes RPI with its own settings (0.6·1 + 0.25·0.88 + 0.15·0)
    assert abs(v["rpi_score"] - (0.6 + 0.25 * 0.88)) < 1e-3


async def test_sync_multipart_with_frames(client, as_role):
    _, h = await as_role("field_responder")
    body = payload("c0b4-0002")
    body["incidents"][0]["detections"][0]["frame_ref"] = "frame_0012.jpg"
    buf = io.BytesIO()
    Image.fromarray(np.zeros((32, 32, 3), np.uint8)).save(buf, "JPEG")
    r = await client.post(
        "/api/v1/sync/incidents",
        data={"payload": json.dumps(body)},
        files={"frame": ("frame_0012.jpg", buf.getvalue(), "image/jpeg")},
        headers=h,
    )
    [res] = r.json()["results"]
    assert res["status"] == "created", r.text
    _, hc = await as_role("incident_commander")
    victims = (
        await client.get(f"/api/v1/incidents/{res['incident_id']}/victims", headers=hc)
    ).json()
    assert victims[0]["media_url"]


async def test_sync_into_linked_web_incident(client, as_role, create_incident):
    _, hc = await as_role("incident_commander")
    web = await create_incident(hc)
    _, h = await as_role("field_responder")
    body = payload("c0b4-0003", linked_incident_id=web["id"])
    [res] = (await client.post("/api/v1/sync/incidents", json=body, headers=h)).json()["results"]
    assert res == {
        "client_uuid": "c0b4-0003",
        "status": "created",
        "incident_id": web["id"],
        "error": None,
    }
    [res2] = (await client.post("/api/v1/sync/incidents", json=body, headers=h)).json()["results"]
    assert res2["status"] == "duplicate"
    victims = (await client.get(f"/api/v1/incidents/{web['id']}/victims", headers=hc)).json()
    assert len(victims) == 1


async def test_sync_errors_are_per_incident(client, as_role):
    _, h = await as_role("field_responder")
    import uuid

    body = payload("c0b4-0004", linked_incident_id=str(uuid.uuid4()))
    [res] = (await client.post("/api/v1/sync/incidents", json=body, headers=h)).json()["results"]
    assert res["status"] == "error" and res["error"] == "incident_not_found"


async def test_sync_requires_mobile_role_and_valid_payload(client, as_role):
    _, ht = await as_role("trainee")
    assert (
        await client.post("/api/v1/sync/incidents", json=payload(), headers=ht)
    ).status_code == 403
    _, h = await as_role("field_responder")
    r = await client.post(
        "/api/v1/sync/incidents", json={"device_id": "x", "incidents": []}, headers=h
    )
    assert r.status_code == 422
